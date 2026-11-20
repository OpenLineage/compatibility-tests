#!/bin/bash

# Runs Hive scenarios on an existing cluster (runner/create_cluster.sh) and records how each one ended in
# <events-dir>/status.json. Each scenario's test/*.sql runs as one Dataproc Hive job; the hook writes the events to GCS
# and they are downloaded to <events-dir>/<scenario>/. Used by CI and by run_hive_dataproc_tests.sh.
#
# A failed scenario doesn't stop the others and doesn't fail this script: it's recorded as FAILED, and validation then
# fails that scenario.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCENARIOS_DIR="${HIVE_SCENARIOS_DIR:-$REPO_ROOT/producer/hive_dataproc/scenarios}"
# shellcheck source=dev/defaults.env
source "$REPO_ROOT/dev/defaults.env"
# shellcheck source=dev/lib/status.sh
source "$REPO_ROOT/dev/lib/status.sh"

usage() {
  cat >&2 <<USAGE
Usage: $0 --cluster-name NAME --events-dir DIR --scenarios 's1;s2' [options]

  --cluster-name NAME          cluster to run on
  --events-dir DIR             events go to <DIR>/<scenario>/, the run status to <DIR>/status.json
  --scenarios LIST             scenarios to run, separated by ';' (see scripts/get_valid_test_scenarios.sh)
  --project PROJECT            GCP project (default $GCP_PROJECT)
  --region REGION              region (default $GCP_REGION)
  --bucket BUCKET              bucket the events are written to (default $GCS_BUCKET)
  --credentials-file PATH      service account key (default: application default credentials)
USAGE
  exit "${1:-1}"
}

warn() {
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::warning::$1"; else echo "WARNING: $1" >&2; fi
}

cluster_name="" events_dir="" scenarios="" credentials_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --events-dir) events_dir="$2"; shift 2 ;;
    --scenarios) scenarios="$2"; shift 2 ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --bucket) GCS_BUCKET="$2"; shift 2 ;;
    --credentials-file) credentials_file="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$cluster_name" && -n "$events_dir" && -n "$scenarios" ]] || usage

mkdir -p "$events_dir"
events_dir="$(cd "$events_dir" && pwd)"
status_file="$events_dir/status.json"
status_init "$status_file"

IFS=';' read -ra scenario_list <<< "$scenarios"
for scenario in "${scenario_list[@]}"; do
  echo "Running Hive scenario: $scenario"
  out="$events_dir/$scenario"
  mkdir -p "$out"
  rm -f "$out"/*.json  # from an earlier local run into the same directory

  query_file=$(find "$SCENARIOS_DIR/$scenario/test/" -maxdepth 1 -type f -name "*.sql" 2> /dev/null | sort | head -n 1)
  if [[ -z "$query_file" ]]; then
    record_status "$status_file" "$scenario" FAILED
    warn "no test/*.sql for Hive scenario $scenario"
    continue
  fi

  # a new GCS prefix per run, so only this run's events are downloaded
  prefix="events/$scenario/$(python3 -c 'import time; print(int(time.time() * 1000))')/"
  properties="hive.openlineage.transport.type=gcs"
  properties+=",hive.openlineage.transport.bucketName=$GCS_BUCKET"
  properties+=",hive.openlineage.transport.fileNamePrefix=$prefix"

  args=(--project-id "$GCP_PROJECT" --region "$GCP_REGION" --cluster-name "$cluster_name" --query "$(cat "$query_file")"
        --output-directory "$out" --properties "$properties")
  [[ -n "$credentials_file" ]] && args+=(--credentials-file "$credentials_file")
  log=$(mktemp)
  if python "$REPO_ROOT/dev/dataproc/dataproc_workflow.py" run-hive-query "${args[@]}" 2>&1 | tee "$log"; then
    state=DONE
  else
    # the job's final state when the job ran (e.g. ERROR), FAILED when it couldn't be submitted or followed
    state=$(sed -n 's/^Hive job .* ended in state \([A-Z_]*\)$/\1/p' "$log" | tail -n 1)
    [[ -z "$state" || "$state" == DONE ]] && state=FAILED
    warn "Hive job for scenario $scenario ended in state $state"
  fi
  job_id=$(sed -n 's/^Submitted Hive job with job_id: //p' "$log" | tail -n 1)
  record_status "$status_file" "$scenario" "$state" "$job_id"
  rm -f "$log"
  echo "Finished scenario $scenario: $state"
done

echo "Run status: $status_file"
