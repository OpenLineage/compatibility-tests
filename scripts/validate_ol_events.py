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
    def __init__(self, schema_validators):
        self.schema_validators = schema_validators

    @staticmethod
    def is_custom_facet(facet, schema_type):
        if facet.get('_schemaURL') is not None:
            is_custom = any(facet.get('_schemaURL').__contains__(f'defs/{facet_type}Facet') for facet_type in
                    ['Run', 'Job', 'Dataset', 'InputDataset', 'OutputDataset'])
            if is_custom:
                print(f"facet {schema_type} seems to be custom facet, validation skipped")
            return is_custom
        return False



    @classmethod
    def get_validators(cls, spec_path, tags):
        return {tag: cls.get_validator(spec_path, tag) for tag in tags}

    @classmethod
    def get_validator(cls, spec_path, tag):
        file_paths = listdir(join(spec_path, tag))
        facet_schemas = [load_json(join(spec_path, tag, path)) for path in file_paths if path.__contains__('Facet.json')]
        spec_schema = next(load_json(join(spec_path, tag, path)) for path in file_paths if path.__contains__('OpenLineage.json'))
        schema_validators = {}
        for schema in facet_schemas:
            name = next(iter(schema['properties']))
            store = {
                spec_schema['$id']: spec_schema,
                schema['$id']: schema,
            }
            resolver = RefResolver(base_uri="", referrer=spec_schema, store=store)
            schema_validators[name] = Draft202012Validator(schema, resolver=resolver)

        schema_validators['core'] = Draft202012Validator(spec_schema)
        return cls(schema_validators)

    def validate_entity(self, instance, schema_type, name):
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
        except Exception:
            print(f"when validating {schema_type}, for instance of {name} following exception occurred \n {traceback.format_exc()}")

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

    args = parser.parse_args()

    event_base_dir = args.event_base_dir
    producer_dir = args.producer_dir
    target = args.target
    component = args.component
    component_version = args.component_version
    openlineage_version = args.openlineage_version
    spec_base_dir = args.spec_base_dir

    return event_base_dir, producer_dir, target, spec_base_dir, component, component_version, openlineage_version


def check_versions(component_version, openlineage_version, config):
    component_versions = config.get("component_versions", {})
    openlineage_versions = config.get("openlineage_versions", {})

    return (release_between(component_version, component_versions.get("min"), component_versions.get("max")) and
            release_between(openlineage_version, openlineage_versions.get("min"), openlineage_versions.get("max")))


def main():
    base_dir, producer_dir, target, spec_dirs, component, component_version, openlineage_version = get_arguments()
    scenarios = {}
    if component == 'scenarios':
        validators = OLSyntaxValidator.get_validators(spec_path=spec_dirs, tags=openlineage_version.split(','))
        for scenario_name in listdir(base_dir):
            scenario_path = get_path(base_dir, component, scenario_name)
            if isdir(scenario_path):
                config = get_config(producer_dir, component, scenario_name)
                validator = validators.get(config.get('openlineage_version'))
                print(f"for scenario {scenario_name} validation version is {config.get('openlineage_version')}")
                result_events = {file: load_json(path) for file in listdir(scenario_path) if
                                 isfile(path := join(scenario_path, file))}
                tests = validate_scenario_syntax(result_events, validator, config)
                scenarios[scenario_name] = Scenario.simplified(scenario_name, tests)
        report = Report({component: Component(component, 'producer', scenarios, "", "")})
    else:
        validator = OLSyntaxValidator.get_validator(spec_path=spec_dirs, tag=openlineage_version)
        for scenario_name in listdir(base_dir):
            config = get_config(producer_dir, component, scenario_name)
            scenario_path = get_path(base_dir, component, scenario_name)
            expected = get_expected_events(producer_dir, component, scenario_name, config, component_version, openlineage_version)
            result_events = {file: load_json(path) for file in listdir(scenario_path) if
                             isfile(path := join(scenario_path, file))}
            tests = validate_scenario_syntax(result_events, validator, config)
            if all_tests_succeeded(tests) and expected is not None:
                for name, res in OLSemanticValidator(expected).validate(result_events).items():
                    tests[name] = res
            scenarios[scenario_name] = Scenario.simplified(scenario_name, tests)
        report = Report({component: Component(component, 'producer', scenarios, component_version, openlineage_version)})
    with open(target, 'w') as f:
        jsonc.dump(report.to_dict(), f, indent=2)


def get_path(base_dir, component, scenario_name):
    if component == 'scenarios':
        return join(base_dir, scenario_name, 'events')
    return join(base_dir, scenario_name)


if __name__ == "__main__":
    main()
