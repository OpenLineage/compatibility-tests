import argparse
import json
from os.path import isfile, join


def get_arguments():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('--failure_path', type=str, help="directory containing the failures file")
    parser.add_argument('--issue_path', type=str, help="target directory")
    args = parser.parse_args()

    return args.failure_path, args.issue_path


def get_failures(components):
    result = ''
    for component in components:
        result += f"## Component: {component['name']}\n"
        consumer_github_maintainers = [maintainer.get('github-name') for maintainer in json.load(
            open(join('consumer', 'consumers', component['name'], 'maintainers.json'), 'r'))
                                       if maintainer.get('github-name') is not None]
        result += "Maintainers for component: " + ' '.join([f"@{cgm}" for cgm in consumer_github_maintainers]) + '  \n'
        for failed in component['scenarios']:
            result += f"### Scenario: {failed['name']}\n"
            scenario_github_maintainers = [maintainer.get('github-name') for maintainer in json.load(
                open(join('consumer', 'consumers', component['name'], 'scenarios', failed['name'],
                          'maintainers.json'), 'r')) if maintainer.get('github-name') is not None]
            result += "Maintainers for scenario: " + ' '.join([f"@{cgm}" for cgm in scenario_github_maintainers if cgm not in consumer_github_maintainers]) + '  \n'
            # result += f"failures in: \n"
            result += '\n'.join([f"name: {t['name']},  \nvalidation_type: {t['validation_type']}  \nentity_type: {t['entity_type']}  \ndetails:  \n\t" + '  \n\t'.join([f"`{d}`" for d in t['details']]) for t in failed['tests']])
    return result


def main():
    issue = '# Failures in automatic tests\n'
    failure_path, issue_path = get_arguments()
    components = json.load(open(failure_path, 'r'))
    issue += get_failures(components)
    t = open(issue_path, 'w')
    t.write(issue)
    t.close()
    print(issue)


if __name__ == "__main__":
    main()