import argparse
import json
import os
import re
import secrets
import time
from pathlib import Path
from os.path import join
from proto import Message
from google.api_core.exceptions import InvalidArgument
from google.oauth2.service_account import Credentials
from google.cloud.datacatalog_lineage_v1 import LineageClient, SearchLinksRequest, EntityReference
from google.protobuf.json_format import ParseDict
from google.protobuf import struct_pb2
from compare_events import diff
from report import Report, Component, Scenario, Test

LINK_INDEXING_TIMEOUT_SECONDS = 240
LINK_RETRY_INTERVAL_SECONDS = 15
MAX_LOGGED_DETAILS = 10
# processes left behind by crashed runs are removed once their token is older than this
STALE_PROCESS_SECONDS = 3 * 60 * 60
# process display names are "<job namespace>:<job name>", the token is appended to the namespace
TOKEN_PATTERN = re.compile(r"-t(\d{10})-[0-9a-f]{4}:")


def log(message):
    # flush explicitly, stdout is block-buffered in CI and the whole log would only show up at exit
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class EntityHandler:

    def __init__(self, client=None, consumer_dir=None, scenario_dir=None, parent=None, release=None):
        self.client = client
        self.consumer_dir = Path(consumer_dir)
        self.scenario_dir = Path(scenario_dir)
        self.parent = parent
        self.release = release
        self.token = None

    def start_scenario(self):
        # runs share one Dataplex project, a unique job namespace per scenario run keeps their processes apart
        self.token = f"t{int(time.time())}-{secrets.token_hex(2)}"
        log(f"Job namespaces suffixed with -{self.token}")

    def is_own(self, process):
        return f"-{self.token}:" in process.display_name

    def strip_token(self, value):
        return value.replace(f"-{self.token}:", ":")

    def load_ol_events(self, scenario):
        scenario_path = self.scenario_dir / scenario / "events"
        entity = [{'name': entry.name, 'payload': self.get_payload(entry)} for entry in scenario_path.iterdir() if
                  entry.is_file()]
        return sorted(entity, key=lambda d: d['name'])

    def get_payload(self, entry):
        event = json.loads(entry.read_text())
        parent = event.get('run', {}).get('facets', {}).get('parent', {})
        for job in [event.get('job'), parent.get('job'), parent.get('root', {}).get('job')]:
            if job and 'namespace' in job:
                job['namespace'] = f"{job['namespace']}-{self.token}"
        return ParseDict(event, struct_pb2.Struct())

    def send_ol_events(self, scenario):
        events = self.load_ol_events(scenario)
        log(f"Sending {len(events)} events")
        report = []
        for e in events:
            try:
                self.client.process_open_lineage_run_event(parent=self.parent, open_lineage=e['payload'])
                report.append((e['name'], []))
                time.sleep(0.5)
            except InvalidArgument as exc:
                log(f"Event {e['name']} rejected: {exc.args[0]}")
                report.append((e['name'], exc.args[0]))
        time.sleep(5)
        return report

    def load_validation_events(self, scenario, config):
        d = {}
        scenario_dir = join(self.consumer_dir, "scenarios", scenario)
        for e in config['tests']:
            name = e['name']
            path = e['path']
            entity = e['entity']
            tags = e['tags']
            d[name] = {'body': json.load(open(join(scenario_dir, path), 'r')), 'entity': entity, 'tags': tags}

        processes = {k: v for k, v in d.items() if v['entity'] == "process"}
        runs = {k: v for k, v in d.items() if v['entity'] == "run"}
        lineage_events = {k: v for k, v in d.items() if v['entity'] == "lineage_event"}
        links = {k: v for k, v in d.items() if v['entity'] == "link"}
        return processes, runs, lineage_events, links

    def dump_api_state(self, scenario):
        dump_directory = self.consumer_dir / "scenarios" / scenario / "api_state"
        dump_directory.mkdir(parents=True, exist_ok=True)

        processes_state, runs_state, events_state, links_state = self.get_api_state()

        self.write_entity_to_file(processes_state, dump_directory, "processes.json")
        self.write_entity_to_file(runs_state, dump_directory, "runs.json")
        self.write_entity_to_file(events_state, dump_directory, "lineage_events.json")
        self.write_entity_to_file(links_state, dump_directory, "links.json")

    def write_entity_to_file(self, processes_state, dump_directory, name):
        with open(dump_directory / name, 'w') as f:
            json.dump(processes_state, f, indent=2)

    def get_api_state(self):
        processes = [Message.to_dict(p) for p in self.client.list_processes(parent=self.parent) if self.is_own(p)]
        for p in processes:
            p['display_name'] = self.strip_token(p['display_name'])
        runs = [Message.to_dict(r) for p in processes for r in self.client.list_runs(parent=p['name'])]
        lineage_events = [Message.to_dict(e) for r in runs for e in self.client.list_lineage_events(parent=r['name'])]
        entities = sorted({fqn for le in lineage_events for link in le['links']
                           for fqn in self.searchable_names(link['source']['fully_qualified_name']) +
                           self.searchable_names(link['target']['fully_qualified_name'])})
        links = [Message.to_dict(res) for fqn in entities for res in self.get_links_from(fqn)]

        values = list({link["name"]: link for link in links}.values())
        log(f"Api state: {len(processes)} processes, {len(runs)} runs, {len(lineage_events)} lineage events, "
            f"{len(values)} links")
        return processes, runs, lineage_events, values

    @staticmethod
    def searchable_names(fqn):
        # Dataplex stores GCS link endpoints at bucket level, so object FQNs (gcs:bucket.`path`) are not searchable
        if fqn.startswith('gcs:') and '.' in fqn:
            return [fqn, fqn.split('.', 1)[0]]
        return [fqn]

    def get_links_from(self, fqn):
        # source and target are a oneof in SearchLinksRequest, setting both silently drops one of them
        return self.client.search_links(
            request=SearchLinksRequest(source=EntityReference(fully_qualified_name=fqn), parent=self.parent))

    def clean_up(self):
        processes = [p for p in self.client.list_processes(parent=self.parent) if self.is_own(p)]
        log(f"Cleaning up {len(processes)} processes")
        for p in processes:
            self.client.delete_process(name=p.name)

    def clean_up_stale(self):
        # only touches processes created by this validator, other runs may be using the project right now
        now = time.time()
        stale = [p for p in self.client.list_processes(parent=self.parent)
                 if (m := TOKEN_PATTERN.search(p.display_name)) and now - int(m.group(1)) > STALE_PROCESS_SECONDS]
        log(f"Cleaning up {len(stale)} stale processes")
        for p in stale:
            self.client.delete_process(name=p.name)

    def read_consumer_config(self, scenario_name):
        return self.read_config(self.consumer_dir / 'scenarios', scenario_name)

    def read_scenario_config(self, scenario_name):
        return self.read_config(self.scenario_dir, scenario_name)

    def read_config(self, directory, scenario):
        path = directory / scenario / "config.json"
        with open(path, 'r') as f:
            return json.load(f)


class Validator:
    @staticmethod
    def validate_syntax(config, errors, scenario_name):
        errors_ = [Test.simplified(name, 'syntax', 'openlineage', details, config) for name, details in
                   errors]
        scenario = Scenario.simplified(scenario_name, errors_)
        return scenario

    @staticmethod
    def validate_api_state(scenario, api_state, validation_events):
        processes_expected, runs_expected, events_expected, links_expected = validation_events
        processes_state, runs_state, events_state, links = api_state
        tests = []
        tests.extend(Validator.compare_by_display_name(processes_expected, processes_state, 'process'))
        tests.extend(Validator.compare_by_display_name(runs_expected, runs_state, 'run'))
        tests.extend(Validator.compare_by_start_time(events_expected, events_state, 'lineage_event'))
        tests.extend(Validator.compare_by_start_time(links_expected, links, 'link'))
        return Scenario.simplified(scenario, tests)

    @staticmethod
    def compare_by_display_name(expected, result, entity_type):
        # ids are derived from the per-run job namespace, so entities are matched by display name
        # (process: "<namespace>:<job name>", run: OpenLineage run id), which may be a template
        results = []
        for k, v in expected.items():
            details = []
            for exp in v['body']:
                label = exp['display_name']
                matched = [r for r in result if not diff(label, r.get('display_name'), ".display_name")]
                if len(matched) > 0:
                    d = [diff(exp, match, "") for match in matched]
                    if not any(len(e) == 0 for e in d):
                        details.extend([f"{entity_type} {label}, {r}" for r in d[0]])
                else:
                    details.append(f"{entity_type} {label}, no matching entity")
            results.append(Test.simplified(entity_type, 'semantics', entity_type, details, v['tags']))
        return results

    @staticmethod
    def compare_by_start_time(expected, result, entity_type):
        results = []
        for k, v in expected.items():
            details = []
            for exp in v['body']:
                matched = [r for r in result if exp['start_time'] == r['start_time']]
                if len(matched) > 0:
                    d = [diff(exp, match, "") for match in matched]
                    diffs = [] if any(len(e) == 0 for e in d) else d[0]
                else:
                    diffs = [f"event {exp['start_time']}, no matching entity"]
                details.extend(diffs)
            results.append(Test.simplified(entity_type, 'semantics', entity_type, details, v['tags']))
        return results


def list_scenarios(consumer_dir):
    return [entry.name for entry in os.scandir(f"{consumer_dir}/scenarios") if entry.is_dir()]


def get_arguments():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('--credentials', type=str, help="credentials for GCP")
    parser.add_argument('--consumer_dir', type=str, help="Path to the consumer directory")
    parser.add_argument('--scenario_dir', type=str, help="Path to the scenario directory")
    parser.add_argument('--parent', type=str, help="Parent identifier")
    parser.add_argument('--release', type=str, help="OpenLineage release used in generating events")
    parser.add_argument("--dump", action='store_true', help="dump api state")
    parser.add_argument("--target", type=str, help="target location")

    args = parser.parse_args()

    credentials = Credentials.from_service_account_file(args.credentials)
    client = LineageClient(credentials=credentials)
    consumer_dir = args.consumer_dir
    scenario_dir = args.scenario_dir
    parent = args.parent
    release = args.release
    dump = args.dump
    target = args.target

    return consumer_dir, scenario_dir, parent, client, release, dump, target


def failed_tests(scenario):
    return sorted(name for name, test in scenario.tests.items() if test.status == "FAILURE")


def log_failures(scenario, api_state):
    for name in failed_tests(scenario):
        details = scenario.tests[name].details
        log(f"  {name} failed with {len(details)} differences:")
        for d in details[:MAX_LOGGED_DETAILS]:
            log(f"    {d}")
        if len(details) > MAX_LOGGED_DETAILS:
            log(f"    ... {len(details) - MAX_LOGGED_DETAILS} more in the report")
    if "lineage_event" in failed_tests(scenario) or "link" in failed_tests(scenario):
        _, _, lineage_events, links = api_state
        log("  actual lineage event links:")
        for le in sorted(lineage_events, key=lambda e: e['start_time']):
            for link in le['links']:
                log(f"    {le['start_time']}: {link['source']['fully_qualified_name']} -> "
                    f"{link['target']['fully_qualified_name']}")
        log("  actual searched links:")
        for link in links:
            log(f"    {link['start_time']}: {link['source']['fully_qualified_name']} -> "
                f"{link['target']['fully_qualified_name']}")


def validate_with_link_retries(validator, handler, scenario_name, validation_events):
    # links are indexed asynchronously, usually 45-120s after the events are processed,
    # everything else is available right away, so only wait while links are the only failure
    start = time.time()
    attempt = 1
    while True:
        api_state = handler.get_api_state()
        result = validator.validate_api_state(scenario_name, api_state, validation_events)
        failed = failed_tests(result)
        elapsed = int(time.time() - start)
        if not failed:
            log(f"Api state of {scenario_name} valid after {elapsed}s (attempt {attempt})")
            return result
        if failed != ["link"]:
            log(f"Api state of {scenario_name} invalid ({', '.join(failed)}), not waiting for link indexing")
            log_failures(result, api_state)
            return result
        if elapsed + LINK_RETRY_INTERVAL_SECONDS > LINK_INDEXING_TIMEOUT_SECONDS:
            log(f"Links of {scenario_name} still invalid after {elapsed}s, giving up")
            log_failures(result, api_state)
            return result
        log(f"Links of {scenario_name} not indexed yet after {elapsed}s (attempt {attempt}), "
            f"retrying in {LINK_RETRY_INTERVAL_SECONDS}s")
        time.sleep(LINK_RETRY_INTERVAL_SECONDS)
        attempt += 1


def process_scenario(validator, handler, scenario_name, dump):
    start = time.time()
    log(f"=== Processing scenario {scenario_name} ===")
    handler.start_scenario()
    config = handler.read_scenario_config(scenario_name)
    errors = handler.send_ol_events(scenario_name)
    scenario = validator.validate_syntax(config, errors, scenario_name)
    log(f"Syntax validation for {scenario_name}: {scenario.status}")

    if scenario.status == "SUCCESS":
        if dump:
            # links are indexed asynchronously, give them time to show up in the dump
            log(f"Waiting {LINK_INDEXING_TIMEOUT_SECONDS // 2}s for link indexing before dumping {scenario_name}")
            time.sleep(LINK_INDEXING_TIMEOUT_SECONDS / 2)
            handler.dump_api_state(scenario_name)
            log(f"Dumped api state of {scenario_name}")
        else:
            consumer_config = handler.read_consumer_config(scenario_name)
            validation_events = handler.load_validation_events(scenario_name, consumer_config)
            scenario.update(validate_with_link_retries(validator, handler, scenario_name, validation_events))

    handler.clean_up()
    log(f"=== {scenario_name}: {scenario.status} in {int(time.time() - start)}s ===")
    return scenario


def main():
    consumer_dir, scenario_dir, parent, client, release, dump, target = get_arguments()
    validator = Validator()
    handler = EntityHandler(client, consumer_dir, scenario_dir, parent, release)
    scenarios_names = list_scenarios(consumer_dir)
    handler.clean_up_stale()
    scenarios = [process_scenario(validator, handler, scenario, dump) for scenario in scenarios_names]

    component = Component('dataplex', 'consumer', {s.name: s for s in scenarios}, "", "")
    report = Report.single_component_report(component)

    with Path(target).open('w') as t:
        json.dump(report.to_dict(), t, indent=2)


if __name__ == "__main__":
    main()
