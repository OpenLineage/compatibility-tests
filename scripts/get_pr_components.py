"""Decides which components a pull request has to test, from the files it changes.

Usage: gh pr diff <n> --name-only | python scripts/get_pr_components.py >> $GITHUB_OUTPUT

- A change to a component's own files, its workflow, or a shared action/script it uses runs the component for real.
- A change to the validation code runs the cheap components (no cloud) for real, and re-validates the stored events
  of the last release run for the Dataproc producers, so a validator change can't merge without being exercised.
- A component running for real isn't re-validated.

When adding a component, or a shared file a component uses, extend the tables below.
"""
import json
import sys

# component -> path prefixes whose change runs it for real
REAL_RUN_PATHS = {
    "scenarios": [
        "consumer/scenarios/",
        ".github/workflows/check_scenarios.yml",
    ],
    "dataplex": [
        "consumer/consumers/dataplex/",
        ".github/workflows/consumer_dataplex.yml",
        # imported by the dataplex validator
        "scripts/report.py",
        "scripts/compare_events.py",
    ],
    "spark_dataproc": [
        "producer/spark_dataproc/",
        ".github/workflows/producer_spark_dataproc.yml",
        ".github/actions/dataproc_cluster/",
        "scripts/get_valid_test_scenarios.sh",
    ],
    "hive_dataproc": [
        "producer/hive_dataproc/",
        ".github/workflows/producer_hive_dataproc.yml",
        ".github/actions/dataproc_cluster/",
        ".github/actions/get_openlineage_artifacts/",
        ".github/actions/upload_artifacts/",
        "scripts/get_valid_test_scenarios.sh",
    ],
    "dbt": [
        "producer/dbt/",
        ".github/workflows/producer_dbt.yml",
        "scripts/get_valid_test_scenarios.sh",
    ],
}

# code that validates events and builds reports, shared by every component
VALIDATION_PATHS = [
    "scripts/validate_ol_events.py",
    "scripts/report.py",
    "scripts/compare_events.py",
    "scripts/compare_releases.py",
    "scripts/compare_and_merge_reports.py",
    "scripts/requirements.txt",
    ".github/actions/run_event_validation/",
    ".github/workflows/collect_and_compare_reports.yml",
    "dev/validation/",
]
# on a validation change these run for real (cheap) ...
VALIDATION_REAL_RUN = ["dbt", "scenarios"]
# ... and these re-validate their stored events instead of starting clusters
VALIDATION_REVALIDATE = ["spark_dataproc", "hive_dataproc"]

# paths that only need the re-validation (the re-validation itself)
REVALIDATE_ONLY_PATHS = [
    ".github/workflows/revalidate_stored_events.yml",
]


def _touches(paths, prefixes):
    return any(path.startswith(prefix) for path in paths for prefix in prefixes)


def select_components(changed_files):
    paths = [p.strip() for p in changed_files if p.strip()]
    run = {component: _touches(paths, prefixes) for component, prefixes in REAL_RUN_PATHS.items()}

    revalidate = set()
    if _touches(paths, VALIDATION_PATHS):
        for component in VALIDATION_REAL_RUN:
            run[component] = True
        revalidate.update(VALIDATION_REVALIDATE)
    if _touches(paths, REVALIDATE_ONLY_PATHS):
        revalidate.update(VALIDATION_REVALIDATE)

    revalidate = sorted(c for c in revalidate if not run[c])
    return {"run": run, "revalidate": revalidate, "any_run": any(run.values()) or bool(revalidate)}


def to_github_outputs(selection):
    lines = [f"{component}_changed={str(value).lower()}" for component, value in selection["run"].items()]
    lines.append(f"revalidate={json.dumps(selection['revalidate'], separators=(',', ':'))}")
    lines.append(f"any_changed={str(selection['any_run']).lower()}")
    return lines


def main():
    changed_files = sys.stdin.read().splitlines()
    for line in to_github_outputs(select_components(changed_files)):
        print(line)
    # for the job log
    print(f"changed files: {len(changed_files)}", file=sys.stderr)


if __name__ == "__main__":
    main()
