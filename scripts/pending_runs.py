"""Tracks the parts of the release check that produced no result, so later scheduled runs retry them.

A part is a (component, component_version, openlineage_version) triple; consumers (dataplex, scenarios) have empty
versions. A planned part is done when a collected report has its entry; otherwise it stays pending in
generated-files/pending_runs.json, which get_release_matrices.sh adds to the next run's matrices.

  plan    the parts a run is going to test, from the effective matrices (pairs without a valid scenario are left out,
          they can never produce a report)
  update  the new pending list, from the planned parts, the collected reports and the old pending list

Only the standard library is used, so it runs before any dependencies are installed.
"""
import argparse
import json
import os
from pathlib import Path

from compare_releases import release_between

# written by compare_and_merge_reports.py or downloaded next to the component reports, not component results
NOT_COMPONENT_REPORTS = {"report.json", "updated-report.json", "new-report.json", "retention-failures-report.json"}


def _key(component, component_version, openlineage_version):
    return component, component_version or "", openlineage_version or ""


def _part_key(part):
    return _key(part["component"], part["component_version"], part["openlineage_version"])


def _has_valid_scenario(producer_dir, component, component_version, openlineage_version):
    scenarios_dir = Path(producer_dir) / component / "scenarios"
    for config_path in sorted(scenarios_dir.glob("*/config.json")):
        config = json.loads(config_path.read_text())
        cvs = config.get("component_versions", {})
        ols = config.get("openlineage_versions", {})
        if (release_between(component_version, cvs.get("min"), cvs.get("max")) and
                release_between(openlineage_version, ols.get("min"), ols.get("max"))):
            return True
    return False


def plan(matrices, run_scenarios, run_dataplex, producer_dir):
    """matrices: {component: {"component_version": [...], "openlineage_versions": [...]} or None/"" when not running}"""
    parts = []
    for component, matrix in matrices.items():
        if not matrix:
            continue
        for cv in matrix["component_version"]:
            for ol in matrix["openlineage_versions"]:
                if _has_valid_scenario(producer_dir, component, cv, ol):
                    parts.append({"component": component, "component_version": cv, "openlineage_version": ol})
    if run_dataplex:
        parts.append({"component": "dataplex", "component_version": "", "openlineage_version": ""})
    if run_scenarios:
        parts.append({"component": "scenarios", "component_version": "", "openlineage_version": ""})
    return sorted(parts, key=_part_key)


def read_reports(reports_dir):
    entries = []
    for path in sorted(Path(reports_dir).iterdir()):
        if path.is_file() and path.name.endswith("-report.json") and path.name not in NOT_COMPONENT_REPORTS:
            entries.extend(json.loads(path.read_text()))
    return entries


def update(planned, report_entries, old_pending, run_url):
    done = {_key(e["name"], e.get("component_version"), e.get("openlineage_version")) for e in report_entries}
    planned_keys = {_part_key(p) for p in planned}
    old_by_key = {_part_key(p): p for p in old_pending}

    pending = []
    for key, entry in old_by_key.items():
        if key not in planned_keys:
            pending.append(entry)  # not attempted this run, unchanged
    for part in planned:
        key = _part_key(part)
        if key in done:
            continue
        previous = old_by_key.get(key)
        pending.append({
            **part,
            "failures": (previous["failures"] if previous else 0) + 1,
            "first_failed_run": previous["first_failed_run"] if previous else run_url,
            "last_failed_run": run_url,
        })
    return sorted(pending, key=_part_key)


def summary(pending):
    if not pending:
        return "No parts without a result.\n"
    lines = ["### Parts without a result (retried by the next scheduled run)", "",
             "| Component | Component version | OpenLineage | Failed runs in a row | Since |", "|---|---|---|---|---|"]
    for p in pending:
        lines.append(f"| {p['component']} | {p['component_version'] or '-'} | {p['openlineage_version'] or '-'} | "
                     f"{p['failures']} | [run]({p['first_failed_run']}) |")
    return "\n".join(lines) + "\n"


def _load_matrix(value):
    value = (value or "").strip()
    return json.loads(value) if value else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="write the planned parts of this run")
    for component in ["spark_dataproc", "hive_dataproc", "dbt"]:
        p.add_argument(f"--{component.replace('_', '-')}-matrix", default="", help=f"{component} matrix JSON, empty when not running")
    p.add_argument("--run-scenarios", default="false")
    p.add_argument("--run-dataplex", default="false")
    p.add_argument("--producer-dir", default="producer")
    p.add_argument("--out", required=True)

    u = sub.add_parser("update", help="write the new pending list")
    u.add_argument("--planned", required=True)
    u.add_argument("--reports-dir", required=True)
    u.add_argument("--pending", required=True, help="the current pending_runs.json")
    u.add_argument("--run-url", required=True)
    u.add_argument("--out", required=True)
    u.add_argument("--summary", default=None, help="file to append a Markdown summary to (e.g. $GITHUB_STEP_SUMMARY)")

    args = parser.parse_args()
    if args.command == "plan":
        matrices = {
            "spark_dataproc": _load_matrix(args.spark_dataproc_matrix),
            "hive_dataproc": _load_matrix(args.hive_dataproc_matrix),
            "dbt": _load_matrix(args.dbt_matrix),
        }
        planned = plan(matrices, args.run_scenarios == "true", args.run_dataplex == "true", args.producer_dir)
        Path(args.out).write_text(json.dumps(planned, indent=2) + "\n")
        print(json.dumps(planned, indent=2))
    else:
        planned = json.loads(Path(args.planned).read_text())
        old_pending = json.loads(Path(args.pending).read_text()) if os.path.exists(args.pending) else []
        pending = update(planned, read_reports(args.reports_dir), old_pending, args.run_url)
        Path(args.out).write_text(json.dumps(pending, indent=2) + "\n")
        text = summary(pending)
        print(text)
        if args.summary:
            with open(args.summary, "a") as f:
                f.write(text)


if __name__ == "__main__":
    main()
