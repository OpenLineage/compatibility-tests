import argparse
import traceback

import jsonc
import logging
import os
import re

from jsonschema.exceptions import best_match, by_relevance
from os import listdir
from os.path import isfile, join, isdir
from jsonschema import Draft202012Validator
from report import Test, Scenario, Component, Report
from compare_releases import release_between
from compare_events import diff
from jsonschema import RefResolver

class OLSyntaxValidator:

    def __init__(self, schema_validators, unchecked_facets=None, openlineage_version=None):
        self.schema_validators = schema_validators
        self.unchecked_facets = unchecked_facets or {}
        self.openlineage_version = openlineage_version

    @staticmethod
    def is_custom_facet(facet, schema_type):
        if facet.get('_schemaURL') is not None:
            is_custom = any(facet.get('_schemaURL').__contains__(f'defs/{facet_type}Facet') for facet_type in
                    ['Run', 'Job', 'Dataset', 'InputDataset', 'OutputDataset'])
            # common package facets without a loaded schema: dbt-model-dataset has no published schema,
            # dbt-version-run and dbt-run-run schemas are only collected for OpenLineage >= 1.40 (src/ layout),
            # newer releases validate them through is_facet
            is_common = any(facet.get('_schemaURL').__contains__(f'schema/{facet_type}-facet.json') for facet_type in
                            ['dbt-version-run', 'dbt-run-run', 'dbt-model-dataset'])
            if is_custom or is_common:
                print(f"facet {schema_type} seems to be custom facet, validation skipped")
                return True
        return False

    @staticmethod
    def is_facet(path):
        # List of facets from the common package that can be used for syntax validation
        common_facets = ['dbt-node-job-facet.json', 'dbt-version-run-facet.json', 'dbt-run-run-facet.json']
        return 'Facet.json' in path or path in common_facets

    @classmethod
    def get_validators(cls, spec_path, tags):
        return {tag: cls.get_validator(spec_path, tag) for tag in tags}

    @classmethod
    def get_validator(cls, spec_path, tag, unchecked_facets=None):
        file_paths = listdir(join(spec_path, tag))
        facet_schemas = { path: load_json(join(spec_path, tag, path)) for path in file_paths if cls.is_facet(path) }
        spec_schema = next(load_json(join(spec_path, tag, path)) for path in file_paths if path.__contains__('OpenLineage.json'))
        schema_validators = {}
        for path, schema in facet_schemas.items():
            try:
                name = next(iter(schema['properties']))
                store = {
                    spec_schema['$id']: spec_schema,
                    schema['$id']: schema,
                }
                resolver = RefResolver(base_uri="", referrer=spec_schema, store=store)
                schema_validators[name] = Draft202012Validator(schema, resolver=resolver)
            except KeyError as e:
                print(f"WARNING: Cannot create schema validator for '{path}' due to missing key:", e)

        schema_validators['core'] = Draft202012Validator(spec_schema)
        return cls(schema_validators, unchecked_facets, tag)

    def validate_entity(self, instance, schema_type, name):
        # Check if this facet should be skipped for the current version
        if self.should_skip_facet(schema_type):
            print(f"Skipping validation for facet '{schema_type}' in version {self.openlineage_version} (unchecked_facets)")
            return []

        try:
            schema_validator = self.schema_validators.get(schema_type)
            if schema_validator is not None:
                errors = [error for error in schema_validator.iter_errors(instance)]
                if len(errors) == 0:
                    return []
                else:
                    return [f"{(e := best_match([error], by_relevance())).json_path}: {e.message}" for error in errors]
            elif self.is_custom_facet(instance.get(schema_type), schema_type):
                # facet type may be custom facet without available schema json file (defined only as class)
                return []
            else:
                return [f"$.{schema_type} facet type {schema_type} not recognized"]
        except Exception as e:
            # a validator that can't check the facet must fail the event, not drop the result
            print(f"when validating {schema_type}, for instance of {name} following exception occurred \n {traceback.format_exc()}")
            return [f"validator error while checking {schema_type}: {type(e).__name__}: {e}"]

    def should_skip_facet(self, facet_name):
        if not self.unchecked_facets or not self.openlineage_version:
            return False

        if facet_name in self.unchecked_facets:
            excluded_versions = self.unchecked_facets[facet_name]
            if self.openlineage_version in excluded_versions:
                return True

        return False

    def validate(self, event, name):
        validation_result = []
        run_validation = self.validate_entity(event, 'core', name)
        run = self.validate_entity_map(event, 'run', name)
        job = self.validate_entity_map(event, 'job', name)
        inputs = self.validate_entity_array(event, 'inputs', 'facets', name)
        input_ifs = self.validate_entity_array(event, 'inputs', 'inputFacets', name)
        outputs = self.validate_entity_array(event, 'outputs', 'facets', name)
        output_ofs = self.validate_entity_array(event, 'outputs', 'outputFacets', name)

        validation_result.extend(run_validation)
        validation_result.extend(run)
        validation_result.extend(job)
        validation_result.extend(inputs)
        validation_result.extend(input_ifs)
        validation_result.extend(outputs)
        validation_result.extend(output_ofs)

        return validation_result

    def validate_entity_array(self, data, entity, generic_facet_type, name):
        return [e.replace('$', f'$.{entity}[{ind}].facets')
                for ind, i in enumerate(data[entity])
                for k, v in (i.get(generic_facet_type).items() if generic_facet_type in i else {}.items())
                for e in self.validate_entity({k: v}, k, name)]

    def validate_entity_map(self, data, entity, name):
        return [e.replace('$', f'$.{entity}.facets') for k, v in data[entity]['facets'].items() for e in
                self.validate_entity({k: v}, k, name)]


class OLSemanticValidator:
    def __init__(self, expected_events):
        self.expected_events = expected_events

    def validate(self, events):
        tests = {}
        for name, event, tags in self.expected_events:
            details = self.validate_event(event, events)
            if details is None:
                details = ['one or more of .eventType, .job.name, .job.namespace not defined in expected event']
            named_details = [f"'{name}' {detail}" for detail in details]
            tests[name] = Test.simplified(name, 'semantics', 'openlineage', named_details, tags)
        return tests

    def validate_event(self, ee, events):
        if 'job' in ee and 'eventType' in ee and 'name' in ee['job'] and 'namespace' in ee['job']:
            found = [
                f"event with .eventType: {ee['eventType']}, .job.name: {ee['job']['name']} and .job.namespace: {ee['job']['namespace']} not found in result events"]
            for e in events.values():
                event_types_match = self.fields_match(e['eventType'], ee['eventType'])
                names_match = self.fields_match(e['job']['name'], ee['job']['name'])
                namespaces_match = self.fields_match(e['job']['namespace'], ee['job']['namespace'])
                if event_types_match and names_match and namespaces_match and len(found) > 0:
                    found = diff(ee, e)
            return found
        return None

    @staticmethod
    def fields_match(r, e) -> bool:
        if e == r:
            return True

        # if the expected field is jinja
        regex = re.compile(r"^\{\{\s*match\(result,\s*(['\"])(.*?)\1\s*\)\s*\}\}$")

        pattern_match = regex.match(e)

        if pattern_match:
            # Extract the actual regex pattern from e
            pattern = pattern_match.group(2)
            # Check if r matches the regex pattern
            return re.fullmatch(pattern, r) is not None

        return False


def load_json(path):
    with open(path) as f:
        return jsonc.load(f)


def extract_pattern(identifier, patterns):
    if patterns is not None:
        for pattern in patterns:
            match = re.search(pattern, identifier)
            if match:
                return match.group(0)
    return identifier


def get_event_identifier(event, default, patterns):
    if 'job' in event and 'eventType' in event and 'name' in event['job'] and 'namespace' in event['job']:
        return f"{event['job']['namespace']}:{extract_pattern(event['job']['name'], patterns)}:{event['eventType']}"
    else:
        return default


def all_tests_succeeded(syntax_tests):
    return not any(t.status == "FAILURE" for t in syntax_tests.values())


def get_expected_events(producer_dir, component, scenario_name, config, component_version, openlineage_version):
    test_events = []
    for test in config['tests']:
        if check_versions(component_version, openlineage_version, test):
            filepath = join(producer_dir, component, 'scenarios', scenario_name, test['path'])
            body = load_json(filepath)
            test_events.append((test['name'], body, test['tags']))
    return test_events


def validate_scenario_syntax(result_events, validator, config):
    syntax_tests = {}
    for name, event in result_events.items():
        identification = get_event_identifier(event, name, config.get('patterns'))
        print(f"syntax validation for {identification}")
        details = validator.validate(event, name)
        syntax_tests[identification] = Test(identification, "FAILURE" if len(details) > 0 else "SUCCESS",
                                            'syntax', 'openlineage', details, {})
    return syntax_tests


def get_config(producer_dir, component, scenario_name):
    if component == 'scenarios':
        path = join(producer_dir, 'scenarios', scenario_name, 'config.json')
    else:
        path = join(producer_dir, component, 'scenarios', scenario_name, 'config.json')
    with open(path) as f:
        return jsonc.load(f)


def get_arguments():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('--event_base_dir', type=str, help="directory containing the reports")
    parser.add_argument('--spec_base_dir', type=str, help="directory containing specs and facets")
    parser.add_argument('--producer_dir', type=str, help="directory storing producers")
    parser.add_argument('--component', type=str, help="component producing the validated events")
    parser.add_argument('--component_version', type=str, help="component release used in generating events")
    parser.add_argument('--openlineage_version', type=str, help="Comma separated list of Openlineage versions")
    parser.add_argument('--target', type=str, help="target file")
    parser.add_argument('--openlineage_release', type=str, default=None,
                        help="OpenLineage release used for version gating when --openlineage_version is a spec tag "
                             "that isn't a version (e.g. main for snapshots)")
    parser.add_argument('--run_status', type=str, default=None,
                        help="status.json of the producer run: [{scenario, state, job_id}], state DONE when the job finished")

    args = parser.parse_args()

    event_base_dir = args.event_base_dir
    producer_dir = args.producer_dir
    target = args.target
    component = args.component
    component_version = args.component_version
    openlineage_version = args.openlineage_version
    spec_base_dir = args.spec_base_dir

    return (event_base_dir, producer_dir, target, spec_base_dir, component, component_version, openlineage_version,
            args.openlineage_release, args.run_status)


def check_versions(component_version, openlineage_version, config):
    component_versions = config.get("component_versions", {})
    openlineage_versions = config.get("openlineage_versions", {})

    return (release_between(component_version, component_versions.get("min"), component_versions.get("max")) and
            release_between(openlineage_version, openlineage_versions.get("min"), openlineage_versions.get("max")))


def failure(name, validation_type, detail):
    return Test(name, 'FAILURE', validation_type, 'openlineage', [detail], {})


def last_line_of_exception():
    return traceback.format_exc().strip().splitlines()[-1]


def load_run_status(path):
    """Producer job states by scenario, from the status.json written by the producer run (if any)."""
    if path is None:
        return {}
    if not isfile(path):
        print(f"WARNING: run status file {path} not found, producer job states are not checked")
        return {}
    return {entry['scenario']: entry for entry in load_json(path)}


def load_events(scenario_path):
    if not isdir(scenario_path):
        return {}
    return {file: load_json(path) for file in listdir(scenario_path) if isfile(path := join(scenario_path, file))}


def valid_scenarios(producer_dir, component, component_version, openlineage_version):
    """Scenarios defined for the component whose version ranges include the validated versions."""
    scenarios_dir = join(producer_dir, component, 'scenarios')
    if not isdir(scenarios_dir):
        return []
    names = []
    for name in listdir(scenarios_dir):
        if not isdir(join(scenarios_dir, name)):
            continue
        try:
            if check_versions(component_version, openlineage_version, get_config(producer_dir, component, name)):
                names.append(name)
        except Exception:
            # an unreadable config is reported as that scenario's validation failure
            names.append(name)
    return names


def validate_producer_scenario(base_dir, producer_dir, spec_dirs, component, component_version, openlineage_version,
                               gating_version, scenario_name):
    config = get_config(producer_dir, component, scenario_name)
    result_events = load_events(get_path(base_dir, component, scenario_name))
    if not result_events:
        return {'events': failure('events', 'syntax', 'scenario produced no events')}

    validator = OLSyntaxValidator.get_validator(spec_path=spec_dirs, tag=openlineage_version,
                                                unchecked_facets=config.get('unchecked_facets'))
    tests = validate_scenario_syntax(result_events, validator, config)
    expected = get_expected_events(producer_dir, component, scenario_name, config, component_version, gating_version)
    if not all_tests_succeeded(tests):
        tests['semantics'] = Test('semantics', 'SKIPPED', 'semantics', 'openlineage',
                                  ['semantic checks skipped because syntax validation failed'], {})
    elif len(expected) == 0:
        tests['semantics'] = Test('semantics', 'WARNING', 'semantics', 'openlineage',
                                  [f"no semantic tests apply to {component} {component_version} / OpenLineage {gating_version}"], {})
    else:
        tests.update(OLSemanticValidator(expected).validate(result_events))
    return tests


def validate_producer(base_dir, producer_dir, spec_dirs, component, component_version, openlineage_version,
                      openlineage_release, run_status):
    # the scenarios come from their definitions, so a scenario without events is reported instead of vanishing
    gating_version = openlineage_release or openlineage_version
    scenario_names = set(valid_scenarios(producer_dir, component, component_version, gating_version))
    scenario_names.update(name for name in listdir(base_dir) if isdir(join(base_dir, name)))
    job_states = load_run_status(run_status)

    scenarios = {}
    for scenario_name in sorted(scenario_names):
        try:
            tests = validate_producer_scenario(base_dir, producer_dir, spec_dirs, component, component_version,
                                               openlineage_version, gating_version, scenario_name)
        except Exception:
            print(f"validation of scenario {scenario_name} failed:\n{traceback.format_exc()}")
            tests = {'validation': failure('validation', 'syntax', f"validation failed: {last_line_of_exception()}")}

        job = job_states.get(scenario_name)
        if job is not None and job.get('state') != 'DONE':
            tests['producer job'] = failure('producer job', 'run',
                                            f"producer job ended in state {job.get('state')}, job '{job.get('job_id', '')}'")
        scenarios[scenario_name] = Scenario.simplified(scenario_name, tests)
    return Report({component: Component(component, 'producer', scenarios, component_version, openlineage_version)})


def validate_consumer_scenarios(base_dir, producer_dir, spec_dirs, component, openlineage_version):
    validators = OLSyntaxValidator.get_validators(spec_path=spec_dirs, tags=openlineage_version.split(','))
    scenarios = {}
    for scenario_name in listdir(base_dir):
        scenario_path = get_path(base_dir, component, scenario_name)
        if not isdir(scenario_path):
            continue
        try:
            config = get_config(producer_dir, component, scenario_name)
            validator = validators.get(config.get('openlineage_version'))
            if 'unchecked_facets' in config:
                validator.unchecked_facets = config['unchecked_facets']
            print(f"for scenario {scenario_name} validation version is {config.get('openlineage_version')}")
            tests = validate_scenario_syntax(load_events(scenario_path), validator, config)
        except Exception:
            print(f"validation of scenario {scenario_name} failed:\n{traceback.format_exc()}")
            tests = {'validation': failure('validation', 'syntax', f"validation failed: {last_line_of_exception()}")}
        scenarios[scenario_name] = Scenario.simplified(scenario_name, tests)
    return Report({component: Component(component, 'producer', scenarios, "", "")})


def main():
    (base_dir, producer_dir, target, spec_dirs, component, component_version, openlineage_version,
     openlineage_release, run_status) = get_arguments()
    if component == 'scenarios':
        report = validate_consumer_scenarios(base_dir, producer_dir, spec_dirs, component, openlineage_version)
    else:
        report = validate_producer(base_dir, producer_dir, spec_dirs, component, component_version, openlineage_version,
                                   openlineage_release, run_status)
    with open(target, 'w') as f:
        jsonc.dump(report.to_dict(), f, indent=2)


def get_path(base_dir, component, scenario_name):
    if component == 'scenarios':
        return join(base_dir, scenario_name, 'events')
    return join(base_dir, scenario_name)


if __name__ == "__main__":
    main()
