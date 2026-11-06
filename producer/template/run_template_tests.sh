#!/bin/bash

# Template of a producer's local run script. Copy it to producer/<producer>/run_<producer>_tests.sh, set PRODUCER, and
# fill in the steps marked TODO. Keep it plain and linear, with the same steps (and the same scripts) as the producer's CI
# workflow, so "Run locally, as CI does" in the producer's README stays true. producer/dbt/run_dbt_tests.sh is a
# complete example.
#
#   1. the environment the scenarios need (a virtualenv, a cluster, ...)
#   2. the scenarios valid for the versions (scripts/get_valid_test_scenarios.sh), or the ones given with --scenarios
#   3. runner/run_scenarios.sh, shared with CI: runs them, writes <events-dir>/<scenario>/*.json and status.json
#   4. dev/validation/validate_locally.sh: validates the events, writes the report, exits 1 if a scenario failed

set -euo pipefail

PRODUCER=template  # TODO: the producer's directory name
PRODUCER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PRODUCER_DIR/../.." && pwd)"

usage() {
  cat >&2 <<USAGE
Usage: $0 --component-version V --openlineage-version OL [options]

  --component-version V      component version (tested versions: producer/$PRODUCER/versions.json)
  --openlineage-version OL   OpenLineage release
  --scenarios 's1;s2'        scenarios to run (default: every scenario valid for the versions)
  --events-dir DIR           where events and status.json go (default: ./$PRODUCER-events-<V>-<OL>)
  --report-dir DIR           where the report goes (default: .); named like the CI artifact
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
events_dir="${events_dir:-$PWD/$PRODUCER-events-$component_version-$ol_version}"
mkdir -p "$report_dir"
report="$(cd "$report_dir" && pwd)/${PRODUCER//_/-}-$component_version-$ol_version-report.json"

echo "== 1. Environment"
# TODO: install or start what the scenarios need for these versions, e.g. a cached virtualenv
# (producer/dbt/run_dbt_tests.sh) or a Dataproc cluster deleted by a trap (dev/dataproc/create_cluster.sh).

echo "== 2. Scenarios"
if [[ -z "$scenarios" ]]; then
  scenarios=$("$REPO_ROOT/scripts/get_valid_test_scenarios.sh" "$PRODUCER_DIR/scenarios" "$component_version" "$ol_version")
  [[ -n "$scenarios" ]] || { echo "No scenario is valid for $PRODUCER $component_version and OpenLineage $ol_version" >&2; exit 1; }
fi
echo "$scenarios"

echo "== 3. Run"
# TODO: write runner/run_scenarios.sh (see producer/dbt/runner/run_scenarios.sh) and call it from the CI workflow too.
# It records each scenario's outcome with record_status from dev/lib/status.sh.
[[ -x "$PRODUCER_DIR/runner/run_scenarios.sh" ]] || { echo "No runner/run_scenarios.sh yet" >&2; exit 1; }
"$PRODUCER_DIR/runner/run_scenarios.sh" --events-dir "$events_dir" --scenarios "$scenarios"

echo "== 4. Validate"
"$REPO_ROOT/dev/validation/validate_locally.sh" --component "$PRODUCER" --component-version "$component_version" \
  --openlineage-version "$ol_version" --events-dir "$events_dir" --report "$report"
