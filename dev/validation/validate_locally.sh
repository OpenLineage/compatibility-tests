#!/bin/bash

# Validates the events of one producer run (one component version x OpenLineage version) the way CI does: the
# OpenLineage spec of that release, scripts/validate_ol_events.py, and the scenarios valid for those versions. Prints
# a status per scenario and exits 1 if any scenario failed.
#
# The OpenLineage clone, the specs and a virtualenv with scripts/requirements.txt are cached in
# ${OL_COMPAT_CACHE:-~/.cache/openlineage-compatibility-tests}, so later runs start quickly.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CACHE_DIR="${OL_COMPAT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/openlineage-compatibility-tests}"

usage() {
  cat >&2 <<USAGE
Usage: $0 --component NAME --component-version V --openlineage-version OL --events-dir DIR [options]

  --component NAME             producer directory name, e.g. spark_dataproc
  --component-version V        version of the component that produced the events
  --openlineage-version OL     OpenLineage release the events were produced with
  --events-dir DIR             <DIR>/<scenario>/*.json, optionally <DIR>/status.json
  --report PATH                where to write the report (default: ./<component>-<V>-<OL>-report.json, the CI artifact name)
  --run-status PATH            status.json of the run (default: <events-dir>/status.json if it exists)
USAGE
  exit "${1:-1}"
}

component="" component_version="" ol_version="" events_dir="" report="" run_status=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --component) component="$2"; shift 2 ;;
    --component-version) component_version="$2"; shift 2 ;;
    --openlineage-version) ol_version="$2"; shift 2 ;;
    --events-dir) events_dir="$2"; shift 2 ;;
    --report) report="$2"; shift 2 ;;
    --run-status) run_status="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$component" && -n "$component_version" && -n "$ol_version" && -n "$events_dir" ]] || usage
[[ -d "$events_dir" ]] || { echo "No such directory: $events_dir" >&2; exit 1; }
report="${report:-$PWD/${component//_/-}-$component_version-$ol_version-report.json}"
[[ -z "$run_status" && -f "$events_dir/status.json" ]] && run_status="$events_dir/status.json"

mkdir -p "$CACHE_DIR"

# specs of the release, from a cached clone of OpenLineage
if [[ ! -f "$CACHE_DIR/specs/$ol_version/OpenLineage.json" ]]; then
  if [[ ! -d "$CACHE_DIR/OpenLineage/.git" ]]; then
    git clone --quiet --filter=blob:none --no-checkout https://github.com/OpenLineage/OpenLineage.git "$CACHE_DIR/OpenLineage"
  fi
  "$REPO_ROOT/dev/validation/get_ol_specs.sh" "$ol_version" "$CACHE_DIR/specs" "$CACHE_DIR/OpenLineage"
fi

# virtualenv with the validator's requirements, reinstalled when they change
venv="$CACHE_DIR/venv"
requirements_hash=$(shasum "$REPO_ROOT/scripts/requirements.txt" | cut -d' ' -f1)
if [[ ! -x "$venv/bin/python" || "$(cat "$venv/.requirements-hash" 2> /dev/null)" != "$requirements_hash" ]]; then
  python3 -m venv "$venv"
  "$venv/bin/python" -m pip install --quiet --upgrade pip
  "$venv/bin/python" -m pip install --quiet -r "$REPO_ROOT/scripts/requirements.txt"
  echo "$requirements_hash" > "$venv/.requirements-hash"
fi

args=(--event_base_dir="$events_dir" --spec_base_dir="$CACHE_DIR/specs" --target="$report" --component="$component"
      --producer_dir="$REPO_ROOT/producer" --openlineage_version="$ol_version" --component_version="$component_version")
[[ -n "$run_status" ]] && args+=(--run_status="$run_status")
"$venv/bin/python" "$REPO_ROOT/scripts/validate_ol_events.py" "${args[@]}" > "$CACHE_DIR/last-validation.log" 2>&1 \
  || { cat "$CACHE_DIR/last-validation.log" >&2; exit 1; }

echo "Report: $report (validator log: $CACHE_DIR/last-validation.log)"
jq -r '.[].scenarios[] | [.name, .status,
         ([.tests[] | select(.status != "SUCCESS") | "\(.status) \(.name): \(.details[0] // "" | .[0:120])"] | join("; "))]
       | @tsv' "$report" | column -t -s $'\t'
! jq -e 'any(.[].scenarios[]; .status == "FAILURE")' "$report" > /dev/null
