#!/bin/bash

# Runs dbt scenarios and records how each one ended in <events-dir>/status.json. Used by CI and by run_dbt_tests.sh.
# dbt-core, dbt-postgres and openlineage-dbt must be installed (dbt-ol on PATH); each scenario's test/run.sh starts a
# Postgres with Docker Compose when none is reachable on localhost:5432.
#
# A failed scenario doesn't stop the others and doesn't fail this script: it's recorded as FAILED, and validation then
# fails that scenario.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCENARIOS_DIR="$REPO_ROOT/producer/dbt/scenarios"
# shellcheck source=dev/lib/status.sh
source "$REPO_ROOT/dev/lib/status.sh"

usage() {
  cat >&2 <<USAGE
Usage: $0 --events-dir DIR --scenarios 's1;s2'

  --events-dir DIR      events go to <DIR>/<scenario>/event-N.json, the run status to <DIR>/status.json
  --scenarios LIST      scenarios to run, separated by ';' (see scripts/get_valid_test_scenarios.sh)
USAGE
  exit "${1:-1}"
}

events_dir="" scenarios=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --events-dir) events_dir="$2"; shift 2 ;;
    --scenarios) scenarios="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$events_dir" && -n "$scenarios" ]] || usage

mkdir -p "$events_dir"
events_dir="$(cd "$events_dir" && pwd)"
status_file="$events_dir/status.json"
status_init "$status_file"

IFS=';' read -ra scenario_list <<< "$scenarios"
for scenario in "${scenario_list[@]}"; do
  run_script="$SCENARIOS_DIR/$scenario/test/run.sh"
  echo "Running dbt scenario: $scenario"
  mkdir -p "$events_dir/$scenario"
  rm -f "$events_dir/$scenario"/event-*.json  # from an earlier local run into the same directory
  if [[ -f "$run_script" ]] && bash "$run_script" "$events_dir/$scenario"; then
    record_status "$status_file" "$scenario" DONE
    echo "Finished scenario: $scenario"
  else
    record_status "$status_file" "$scenario" FAILED
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
      echo "::warning::dbt scenario $scenario failed"
    else
      echo "WARNING: dbt scenario $scenario failed" >&2
    fi
  fi
done

echo "Run status: $status_file"
