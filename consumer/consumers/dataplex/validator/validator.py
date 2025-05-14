import argparse
import json
import os
import time
from pathlib import Path
from os.path import join
from proto import Message
from google.api_core.exceptions import InvalidArgument
from google.oauth2.service_account import Credentials
from google.cloud.datacatalog_lineage_v1 import LineageClient, SearchLinksRequest
from google.protobuf.json_format import ParseDict
from google.protobuf import struct_pb2
from compare_events import diff
from report import Report, Component, Scenario, Test


class EntityHandler:

    def __init__(self, client=None, consumer_dir=None, scenario_dir=None, parent=None, release=None):
        self.client = client
        self.consumer_dir = Path(consumer_dir)
        self.scenario_dir = Path(scenario_dir)
        self.parent = parent
        self.release = release

    def load_ol_events(self, scenario):
        scenario_path = self.scenario_dir / scenario / "events"
        entity = [{'name': entry.name, 'payload': self.get_payload(entry)} for entry in scenario_path.iterdir() if
                  entry.is_file()]
        return sorted(entity, key=lambda d: d['name'])

    def get_payload(self, entry):
        return ParseDict(json.loads(entry.read_text()), struct_pb2.Struct())

    def send_ol_events(self, scenario):
        events = self.load_ol_events(scenario)
        report = []
        for e in events:
            try:
                response = self.client.process_open_lineage_run_event(parent=self.parent, open_lineage=e['payload'])
                report.append((e['name'], []))
                time.sleep(0.5)
            except InvalidArgument as exc:
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
        processes = [Message.to_dict(p) for p in self.client.list_processes(parent=self.parent)]
        runs = [Message.to_dict(r) for p in processes for r in self.client.list_runs(parent=p['name'])]
        lineage_events = [Message.to_dict(e) for r in runs for e in self.client.list_lineage_events(parent=r['name'])]
        links = [Message.to_dict(res) for le in lineage_events for link in le['links'] for res in self.get_links(link)]

        values = list({link["name"]: link for link in links}.values())
        return processes, runs, lineage_events, values

    def get_links(self, link):
        return self.client.search_links(
            request=SearchLinksRequest(source=link["source"], target=link["target"], parent=self.parent))

    def clean_up(self):
        processes = [x for x in self.client.list_processes(parent=self.parent)]
        for p in processes:
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
        tests.extend(Validator.compare_by_name(processes_expected, processes_state, 'process'))
        tests.extend(Validator.compare_by_name(runs_expected, runs_state, 'run'))
        tests.extend(Validator.compare_by_start_time(events_expected, events_state, 'lineage_event'))
        tests.extend(Validator.compare_by_start_time(links_expected, links, 'link'))
        return Scenario.simplified(scenario, tests)

    @staticmethod
    def compare_by_name(expected, result, entity_type):
        results = []
        for k, v in expected.items():
            details = []
            for exp in v['body']:
                entity_name = exp['name'].rsplit('/', 1)
                matched = next((proc for proc in result if proc['name'] == exp['name']), None)
                if matched is not None:
                    res = diff(exp, matched, "")
                    details.extend([f"{entity_type} {entity_name}, {r}" for r in res])
                else:
                    details.append(f"{entity_type} {entity_name}, no matching entity")
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
                    diffs = [] if any(e for e in d if len(e) > 0) else next(e for e in d)
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


def process_scenario(validator, handler, scenario_name, dump):
    print(f"Processing scenario {scenario_name}")
    handler.clean_up()
    config = handler.read_scenario_config(scenario_name)
    print(config)
    errors = handler.send_ol_events(scenario_name)
    print(f"Syntax validation for {scenario_name}")
    scenario = validator.validate_syntax(config, errors, scenario_name)

    if scenario.status == "SUCCESS":
        if dump:
            print(f"Dumping api state of {scenario_name}")
            handler.dump_api_state(scenario_name)
        else:
            consumer_config = handler.read_consumer_config(scenario_name)
            api_state = handler.get_api_state()
            validation_events = handler.load_validation_events(scenario_name, consumer_config)
            print(f"Api state validation for {scenario_name}")
            scenario.update(validator.validate_api_state(scenario_name, api_state, validation_events))

    handler.clean_up()
    return scenario


def main():
    consumer_dir, scenario_dir, parent, client, release, dump, target = get_arguments()
    validator = Validator()
    handler = EntityHandler(client, consumer_dir, scenario_dir, parent, release)
    scenarios_names = list_scenarios(consumer_dir)
    scenarios = [process_scenario(validator, handler, scenario, dump) for scenario in scenarios_names]

    component = Component('dataplex', 'consumer', {s.name: s for s in scenarios}, "", "")
    report = Report.single_component_report(component)

    with Path(target).open('w') as t:
        json.dump(report.to_dict(), t, indent=2)


if __name__ == "__main__":
    main()
