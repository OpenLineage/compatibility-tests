"""Warns about scenarios that never run and component versions that test nothing.

The tested matrix of a producer is its versions.json plus the latest OpenLineage release and, when releases.json
tracks it, the latest component release (what the PR check and the release check run). Reported:
- scenarios whose version ranges match no pair of that matrix (they're silently never tested);
- component versions of the matrix that no scenario covers (a run for them tests nothing).

Prints GitHub warning annotations and a Markdown summary; always exits 0.
"""
import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from compare_releases import release_between


@dataclass
class NeverRunning:
    producer: str
    scenario: str
    config_path: Path


@dataclass
class UncoveredVersion:
    producer: str
    component_version: str


@dataclass
class Gaps:
    never_running: list = field(default_factory=list)
    uncovered_versions: list = field(default_factory=list)


def _in_range(version, version_range):
    version_range = version_range or {}
    return release_between(version, version_range.get("min"), version_range.get("max"))


def _with(values, extra):
    return values + [extra] if extra and extra not in values else values


def find_gaps(producer_dir, latest_ol, latest_components):
    gaps = Gaps()
    for versions_file in sorted(Path(producer_dir).glob("*/versions.json")):
        producer = versions_file.parent.name
        versions = json.loads(versions_file.read_text())
        ols = _with(versions["openlineage_versions"], latest_ol)
        cvs = _with(versions["component_version"], latest_components.get(producer))
        configs = {p.parent.name: (p, json.loads(p.read_text()))
                   for p in sorted(versions_file.parent.glob("scenarios/*/config.json"))}

        covered = set()
        for scenario, (path, config) in configs.items():
            pairs = [(cv, ol) for cv in cvs for ol in ols
                     if _in_range(cv, config.get("component_versions")) and _in_range(ol, config.get("openlineage_versions"))]
            if pairs:
                covered.update(cv for cv, _ in pairs)
            else:
                gaps.never_running.append(NeverRunning(producer, scenario, path))
        gaps.uncovered_versions.extend(UncoveredVersion(producer, cv) for cv in cvs if cv not in covered)
    return gaps


def latest_from_releases(releases_file):
    releases = {r["name"]: r["latest_version"] for r in json.loads(Path(releases_file).read_text())}
    latest_components = {name: version for name, version in releases.items() if version}
    return releases.get("openlineage", ""), latest_components


def summary(gaps):
    if not gaps.never_running and not gaps.uncovered_versions:
        return "Every scenario runs for at least one tested version, and every tested version runs a scenario.\n"
    lines = ["### Scenario coverage gaps", ""]
    if gaps.never_running:
        lines += ["Scenarios that never run (their version ranges match no tested version):", ""]
        lines += [f"- `{g.producer}/{g.scenario}`" for g in gaps.never_running]
        lines.append("")
    if gaps.uncovered_versions:
        lines += ["Tested component versions without any scenario (their runs test nothing):", ""]
        lines += [f"- `{g.producer}` {g.component_version}" for g in gaps.uncovered_versions]
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--producer-dir", default="producer")
    parser.add_argument("--releases", default="generated-files/releases.json")
    parser.add_argument("--latest-ol", default=None, help="latest OpenLineage release (default: from --releases)")
    parser.add_argument("--summary", default=None, help="file to append the Markdown summary to (e.g. $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args()

    latest_ol, latest_components = latest_from_releases(args.releases)
    gaps = find_gaps(args.producer_dir, args.latest_ol or latest_ol, latest_components)
    for g in gaps.never_running:
        print(f"::warning file={g.config_path}::scenario {g.producer}/{g.scenario} never runs: its version ranges "
              f"match no tested component/OpenLineage version")
    for g in gaps.uncovered_versions:
        print(f"::warning file={args.producer_dir}/{g.producer}/versions.json::{g.producer} {g.component_version} is "
              f"tested but no scenario covers it, its runs test nothing")
    text = summary(gaps)
    print(text)
    if args.summary:
        with open(args.summary, "a") as f:
            f.write(text)


if __name__ == "__main__":
    main()
