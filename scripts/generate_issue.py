import argparse
import json
from os.path import isfile, join


def get_failures(components, skip_maintainers=False):
    result = ''
    for component in components:
        result += f"## Component: {component['name']}\n"
        if not skip_maintainers:
            component_path = get_component_path(component)
            consumer_github_maintainers = [maintainer.get('github-name') for maintainer in json.load(
                open(join(component_path, 'maintainers.json'), 'r'))
                                           if maintainer.get('github-name') is not None]
            result += "Maintainers for component: " + ' '.join([f"@{cgm}" for cgm in consumer_github_maintainers]) + '  \n'
        for failed in component['scenarios']:
            result += f"### Scenario: {failed['name']}\n"
            if not skip_maintainers:
                scenario_github_maintainers = [maintainer.get('github-name') for maintainer in
                    json.load(open(get_scenario_path(component_path, failed), 'r')) if maintainer.get('github-name') is not None]
                result += "Maintainers for scenario: " + ' '.join(
                    [f"@{cgm}" for cgm in scenario_github_maintainers if cgm not in consumer_github_maintainers]) + '  \n'
            # result += f"failures in: \n"
            result += '\n'.join(
                [f"name: {t['name']},  \nvalidation_type: {t['validation_type']}  \nentity_type: {t['entity_type']}  \ndetails:  \n\t" +
                 '  \n\t'.join([f"`{d}`" for d in t['details']]) for t in failed['tests']])
            result += '\n'
        result += '\n'
    return result


def get_scenario_path(component_path, failed):
    return join(component_path, 'scenarios', failed['name'], 'maintainers.json')


def get_component_path(component):
    if component['component_type'] == 'consumer':
        return join('consumer', 'consumers', component['name'])
    return join('producer', component['name'])


def get_arguments():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('--failure_path', type=str, help="directory containing the failures file")
    parser.add_argument('--issue_path', type=str, help="target directory")
    parser.add_argument('--skip-maintainers', action='store_true', help="omit maintainer lines from the output")
    args = parser.parse_args()

    return args.failure_path, args.issue_path, args.skip_maintainers


def main():
    issue = '# Failures in automatic tests\n'
    failure_path, issue_path, skip_maintainers = get_arguments()
    components = json.load(open(failure_path, 'r'))
    issue += get_failures(components, skip_maintainers=skip_maintainers)
    t = open(issue_path, 'w')
    t.write(issue)
    t.close()
    print(issue)


if __name__ == "__main__":
    main()
