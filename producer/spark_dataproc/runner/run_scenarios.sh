#!/bin/bash

# Runs Spark scenarios for one OpenLineage version on a cluster made by runner/create_cluster.sh, up to 3 at a time.
# Events go to gs://<bucket>/events/<run key>/<spark>/<openlineage>/<scenario>/, the drivers' output and status.json
# (how each scenario's job ended) to --logs-dir and gs://<bucket>/logs/<run key>/<spark>/<openlineage>/.
# Used by CI (once per OpenLineage version) and by run_spark_dataproc_tests.sh.
#
# A failed scenario doesn't stop the others and doesn't fail this script: its state is in status.json, and validation
# fails that scenario. When the runner itself fails before writing status.json, every scenario is recorded as
# RUNNER_FAILED, which CI treats as "the pair didn't run".
#
# The cloudsql scenario reads the database user and password from POSTGRESQL_USER and POSTGRESQL_PASSWORD.

set -euo pipefail

SPARK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SPARK_DIR/../.." && pwd)"
# shellcheck source=dev/defaults.env
source "$REPO_ROOT/dev/defaults.env"
# shellcheck source=dev/lib/status.sh
source "$REPO_ROOT/dev/lib/status.sh"

usage() {
  cat >&2 <<USAGE
Usage: $0 --cluster-name NAME --spark-release V --ol-release OL --scenarios 's1;s2' --openlineage-jars LIST
          --run-key KEY --logs-dir DIR [options]

  --cluster-name NAME          cluster to run on (runner/create_cluster.sh, with this OpenLineage version)
  --spark-release V            Spark release of the cluster
  --ol-release OL              OpenLineage version to run with
  --scenarios LIST             scenarios to run, separated by ';' (see scripts/get_valid_test_scenarios.sh)
  --openlineage-jars LIST      as given to runner/create_cluster.sh; picks the GCS transport jar of OL
  --run-key KEY                GCS directory of this run under events/ and logs/ (CI: <run id>-<attempt>)
  --logs-dir DIR               local directory for the driver output and status.json
  --events-dir DIR             also download the events to <DIR>/<scenario>/ and copy status.json there
  --scenario-suffix S          spark.scenario.suffix, keeps the tables of concurrent runs apart (default <V>-<OL>, no dots)
  --project PROJECT            GCP project (default $GCP_PROJECT)
  --region REGION              region (default $GCP_REGION)
  --bucket BUCKET              bucket with the jars, for events and logs (default $GCS_BUCKET)
  --credentials-file PATH      service account key (default: application default credentials)
USAGE
  exit "${1:-1}"
}

warn() {
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::warning::$1"; else echo "WARNING: $1" >&2; fi
}

cluster_name="" spark_release="" ol_release="" scenarios="" openlineage_jars="" run_key="" logs_dir="" events_dir=""
scenario_suffix="" credentials_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --spark-release) spark_release="$2"; shift 2 ;;
    --ol-release) ol_release="$2"; shift 2 ;;
    --scenarios) scenarios="$2"; shift 2 ;;
    --openlineage-jars) openlineage_jars="$2"; shift 2 ;;
    --run-key) run_key="$2"; shift 2 ;;
    --logs-dir) logs_dir="$2"; shift 2 ;;
    --events-dir) events_dir="$2"; shift 2 ;;
    --scenario-suffix) scenario_suffix="$2"; shift 2 ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --bucket) GCS_BUCKET="$2"; shift 2 ;;
    --credentials-file) credentials_file="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$cluster_name" && -n "$spark_release" && -n "$ol_release" && -n "$scenarios" && -n "$openlineage_jars" \
   && -n "$run_key" && -n "$logs_dir" ]] || usage
scenario_suffix="${scenario_suffix:-${spark_release//./}-${ol_release//./}}"
pair_dir="$run_key/$spark_release/$ol_release"

# the spark jar is on the master (create_cluster.sh) and goes on the driver classpath; the GCS transport goes through
# --jars: since 1.40.0 it bundles its own Woodstox, which breaks Hadoop's configuration parsing on the system classpath
gcs_transport_jar=$(tr ';' '\n' <<< "$openlineage_jars" | awk -F: -v v="$ol_release" '$1 == v { print $3 }')
[[ -n "$gcs_transport_jar" ]] || { echo "No GCS transport jar for $ol_release in --openlineage-jars" >&2; exit 1; }

properties="spark.scenario.suffix=$scenario_suffix"
[[ -n "${POSTGRESQL_USER:-}" ]] && properties+=",spark.driver.POSTGRESQL_USER=$POSTGRESQL_USER"
[[ -n "${POSTGRESQL_PASSWORD:-}" ]] && properties+=",spark.driver.POSTGRESQL_PASSWORD=$POSTGRESQL_PASSWORD"

IFS=';' read -ra scenario_list <<< "$scenarios"
mkdir -p "$logs_dir"
rm -f "$logs_dir/status.json"
if [[ -n "$events_dir" ]]; then
  for scenario in "${scenario_list[@]}"; do
    rm -rf "${events_dir:?}/$scenario"  # from an earlier local run into the same directory
  done
fi
args=(--project-id "$GCP_PROJECT" --region "$GCP_REGION" --cluster-name "$cluster_name" --gcs-bucket "$GCS_BUCKET"
      --scenarios-dir "$SPARK_DIR/scenarios" --scenarios "$scenarios" --openlineage-jars-dir "/opt/openlineage/$ol_release"
      --jars "gs://$GCS_BUCKET/jars/$gcs_transport_jar" --events-prefix "events/$pair_dir" --spark-properties "$properties"
      --max-concurrency 3 --logs-directory "$logs_dir")
[[ -n "$events_dir" ]] && args+=(--output-directory "$events_dir")
[[ -n "$credentials_file" ]] && args+=(--credentials-file "$credentials_file")

echo "Running scenarios for Spark $spark_release, OpenLineage $ol_release: $scenarios"
python "$REPO_ROOT/dev/dataproc/dataproc_workflow.py" run-scenarios "${args[@]}" \
  || warn "Some scenarios failed for Spark $spark_release, OpenLineage $ol_release"

if [[ ! -f "$logs_dir/status.json" ]]; then
  status_init "$logs_dir/status.json"
  for scenario in "${scenario_list[@]}"; do
    record_status "$logs_dir/status.json" "$scenario" RUNNER_FAILED
  done
fi

gcloud storage cp -r "$logs_dir/*" "gs://$GCS_BUCKET/logs/$pair_dir/" \
  || warn "Could not upload the driver logs of OpenLineage $ol_release"
if [[ -n "$events_dir" ]]; then
  mkdir -p "$events_dir"
  cp "$logs_dir/status.json" "$events_dir/status.json"
fi
echo "Run status: $logs_dir/status.json"
