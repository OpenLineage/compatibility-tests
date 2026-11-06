#!/bin/bash

# Runs the dbt scenarios for one dbt version x OpenLineage version on your machine, the way CI does
# (.github/workflows/producer_dbt.yml), and validates the events. See "Run locally, as CI does" in README.md.
#
#   1. a virtualenv with dbt-core==V, dbt-postgres and openlineage-dbt==OL (cached, reused by later runs)
#   2. the scenarios valid for the versions (scripts/get_valid_test_scenarios.sh), or the ones given with --scenarios
#   3. runner/run_scenarios.sh: runs them, writes events and status.json (starts Postgres with Docker if needed)
#   4. dev/validation/validate_locally.sh: validates the events, writes the report, exits 1 if a scenario failed

set -euo pipefail

DBT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DBT_DIR/../.." && pwd)"
CACHE_DIR="${OL_COMPAT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/openlineage-compatibility-tests}"

usage() {
  cat >&2 <<USAGE
Usage: $0 --component-version V --openlineage-version OL [options]

  --component-version V      dbt-core version, e.g. 1.8.0 (tested versions: producer/dbt/versions.json)
  --openlineage-version OL   openlineage-dbt version, e.g. 1.55.0
  --scenarios 's1;s2'        scenarios to run (default: every scenario valid for the versions)
  --events-dir DIR           where events and status.json go (default: ./dbt-events-<V>-<OL>)
  --report-dir DIR           where the report goes (default: .); named dbt-<V>-<OL>-report.json like the CI artifact

Environment: PYTHON (default python3) creates the virtualenv; OL_COMPAT_CACHE moves the cache
(default ~/.cache/openlineage-compatibility-tests).
USAGE
  exit "${1:-1}"
}

component_version="" ol_version="" scenarios="" events_dir="" report_dir="."
while [[ $# -gt 0 ]]; do
  case "$1" in
    --component-version) component_version="$2"; shift 2 ;;
    --openlineage-version) ol_version="$2"; shift 2 ;;
    --scenarios) scenarios="$2"; shift 2 ;;
    --events-dir) events_dir="$2"; shift 2 ;;
    --report-dir) report_dir="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$component_version" && -n "$ol_version" ]] || usage
events_dir="${events_dir:-$PWD/dbt-events-$component_version-$ol_version}"
mkdir -p "$report_dir"
report="$(cd "$report_dir" && pwd)/dbt-$component_version-$ol_version-report.json"

echo "== 1. dbt $component_version, openlineage-dbt $ol_version"
venv="$CACHE_DIR/venvs/dbt-$component_version-openlineage-$ol_version"
if [[ ! -x "$venv/bin/dbt-ol" ]]; then
  rm -rf "$venv"
  "${PYTHON:-python3}" -m venv "$venv"
  "$venv/bin/python" -m pip install --quiet --upgrade pip
  # the same packages as the "Install dbt dependencies" step in CI
  "$venv/bin/python" -m pip install --quiet "dbt-core==$component_version" dbt-postgres "openlineage-dbt==$ol_version"
fi
echo "virtualenv: $venv"

echo "== 2. Scenarios"
if [[ -z "$scenarios" ]]; then
  scenarios=$("$REPO_ROOT/scripts/get_valid_test_scenarios.sh" "$DBT_DIR/scenarios" "$component_version" "$ol_version")
  [[ -n "$scenarios" ]] || { echo "No scenario is valid for dbt $component_version and OpenLineage $ol_version" >&2; exit 1; }
fi
echo "$scenarios"

echo "== 3. Run"
PATH="$venv/bin:$PATH" "$DBT_DIR/runner/run_scenarios.sh" --events-dir "$events_dir" --scenarios "$scenarios"

echo "== 4. Validate"
"$REPO_ROOT/dev/validation/validate_locally.sh" --component dbt --component-version "$component_version" \
  --openlineage-version "$ol_version" --events-dir "$events_dir" --report "$report"
