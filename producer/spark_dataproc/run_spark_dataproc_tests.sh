#!/bin/bash

# Runs the Spark scenarios for one Spark version x OpenLineage version on a Dataproc cluster, the way CI does
# (.github/workflows/producer_spark_dataproc.yml), and validates the events. See "Run locally, as CI does" in README.md.
#
#   1. a virtualenv with dev/dataproc/requirements.txt (cached, reused by later runs)
#   2. the scenarios valid for the versions (scripts/get_valid_test_scenarios.sh), or the ones given with --scenarios
#   3. runner/stage_openlineage_jars.sh: the OpenLineage spark and GCS transport jars in gs://<bucket>/jars
#   4. runner/create_cluster.sh: a cluster named after you; deleted at the end, also when a step fails
#   5. runner/run_scenarios.sh: runs the scenarios, downloads the events and driver logs, writes status.json
#   6. dev/validation/validate_locally.sh: validates the events, writes the report, exits 1 if a scenario failed

set -euo pipefail

SPARK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SPARK_DIR/../.." && pwd)"
CACHE_DIR="${OL_COMPAT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/openlineage-compatibility-tests}"
# the expected events match the cluster name of CI's clusters, so local clusters start the same way
CLUSTER_PREFIX=dataproc-producer-test
# shellcheck source=dev/defaults.env
source "$REPO_ROOT/dev/defaults.env"
# shellcheck source=dev/lib/dataproc_venv.sh
source "$REPO_ROOT/dev/lib/dataproc_venv.sh"

usage() {
  cat >&2 <<USAGE
Usage: $0 --component-version V --openlineage-version OL [options]

  --component-version V        Spark version, a key of "releases" in runner/cluster.json (e.g. 3.5.1)
  --openlineage-version OL     OpenLineage release, e.g. 1.55.0
  --scenarios 's1;s2'          scenarios to run (default: every scenario valid for the versions)
  --spark-jar PATH             openlineage-spark jar to test instead of the release from Maven (e.g. a local build);
                               the GCS transport is still the release OL
  --cluster-name NAME          run on this existing cluster, made by runner/create_cluster.sh with the same OpenLineage
                               version; it isn't created or deleted
  --keep-cluster               don't delete the cluster at the end (delete it later with dev/dataproc/delete_cluster.sh)
  --events-dir DIR             where events and status.json go (default: ./spark-dataproc-events-<V>-<OL>)
  --logs-dir DIR               where the driver logs go (default: ./spark-dataproc-logs-<V>-<OL>)
  --report-dir DIR             where the report goes (default: .); named spark-dataproc-<V>-<OL>-report.json like the CI artifact
  --project PROJECT            GCP project (default $GCP_PROJECT)
  --region REGION              region (default $GCP_REGION)
  --bucket BUCKET              bucket for jars, init actions, events and logs (default $GCS_BUCKET)

Credentials: the application default credentials (gcloud auth application-default login) and the gcloud CLI login.
The cloudsql scenario needs POSTGRESQL_USER and POSTGRESQL_PASSWORD (the database of the test project).
Environment: PYTHON (default python3) creates the virtualenv; OL_COMPAT_CACHE moves the cache
(default ~/.cache/openlineage-compatibility-tests).
USAGE
  exit "${1:-1}"
}

component_version="" ol_version="" scenarios="" spark_jar="" cluster_name="" keep_cluster=false events_dir="" logs_dir=""
report_dir="."
while [[ $# -gt 0 ]]; do
  case "$1" in
    --component-version) component_version="$2"; shift 2 ;;
    --openlineage-version) ol_version="$2"; shift 2 ;;
    --scenarios) scenarios="$2"; shift 2 ;;
    --spark-jar) spark_jar="$2"; shift 2 ;;
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --keep-cluster) keep_cluster=true; shift ;;
    --events-dir) events_dir="$2"; shift 2 ;;
    --logs-dir) logs_dir="$2"; shift 2 ;;
    --report-dir) report_dir="$2"; shift 2 ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --bucket) GCS_BUCKET="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$component_version" && -n "$ol_version" ]] || usage
pair="$component_version-$ol_version"
events_dir="${events_dir:-$PWD/spark-dataproc-events-$pair}"
logs_dir="${logs_dir:-$PWD/spark-dataproc-logs-$pair}"
mkdir -p "$report_dir"
report="$(cd "$report_dir" && pwd)/spark-dataproc-$pair-report.json"
gcp=(--project "$GCP_PROJECT" --region "$GCP_REGION" --bucket "$GCS_BUCKET")

echo "== 1. Dataproc client"
dataproc_venv "$CACHE_DIR"

echo "== 2. Scenarios"
if [[ -z "$scenarios" ]]; then
  scenarios=$("$REPO_ROOT/scripts/get_valid_test_scenarios.sh" "$SPARK_DIR/scenarios" "$component_version" "$ol_version")
  [[ -n "$scenarios" ]] || { echo "No scenario is valid for Spark $component_version and OpenLineage $ol_version" >&2; exit 1; }
fi
echo "$scenarios"
if [[ "$scenarios" == *cloudsql* && ( -z "${POSTGRESQL_USER:-}" || -z "${POSTGRESQL_PASSWORD:-}" ) ]]; then
  echo "WARNING: POSTGRESQL_USER / POSTGRESQL_PASSWORD aren't set, the cloudsql scenario will fail" >&2
fi

echo "== 3. OpenLineage jars"
openlineage_jars=$("$SPARK_DIR/runner/stage_openlineage_jars.sh" --jars-dir "gs://$GCS_BUCKET/jars" "$ol_version")
if [[ -n "$spark_jar" ]]; then
  # a local build: a directory per content, so it never reuses (or replaces) another jar with the same name
  local_dir="local/$(shasum "$spark_jar" | cut -c1-12)"
  "$REPO_ROOT/dev/dataproc/gcs_upload.sh" "$spark_jar" "gs://$GCS_BUCKET/jars/$local_dir" > /dev/null
  IFS=':' read -r _ _ gcs_jar <<< "$openlineage_jars"
  openlineage_jars="$ol_version:$local_dir/$(basename "$spark_jar"):$gcs_jar"
fi
echo "$openlineage_jars"

if [[ -n "$cluster_name" ]]; then
  echo "== 4. Using the existing cluster $cluster_name"
else
  echo "== 4. Cluster"
  cluster_name="$CLUSTER_PREFIX-$(dataproc_user_slug)-${component_version//./}-$(date +%s)"
  if [[ "$keep_cluster" == "true" ]]; then
    echo "The cluster is kept; delete it with: dev/dataproc/delete_cluster.sh --cluster-name $cluster_name"
  else
    # shellcheck disable=SC2064  # expand now: the names are fixed from here on
    trap "'$REPO_ROOT/dev/dataproc/delete_cluster.sh' --cluster-name '$cluster_name' --project '$GCP_PROJECT' --region '$GCP_REGION'" EXIT
  fi
  "$SPARK_DIR/runner/create_cluster.sh" --spark-release "$component_version" --cluster-name "$cluster_name" \
    --openlineage-jars "$openlineage_jars" "${gcp[@]}"
fi

echo "== 5. Run"
# its own GCS directory and table suffix, so it doesn't mix with CI or earlier runs on the same cluster
run_key="local-$(dataproc_user_slug)-$(date +%s)"
"$SPARK_DIR/runner/run_scenarios.sh" --cluster-name "$cluster_name" --spark-release "$component_version" \
  --ol-release "$ol_version" --scenarios "$scenarios" --openlineage-jars "$openlineage_jars" --run-key "$run_key" \
  --logs-dir "$logs_dir" --events-dir "$events_dir" \
  --scenario-suffix "$(dataproc_user_slug)-${component_version//./}-${ol_version//./}" "${gcp[@]}"

echo "== 6. Validate"
"$REPO_ROOT/dev/validation/validate_locally.sh" --component spark_dataproc --component-version "$component_version" \
  --openlineage-version "$ol_version" --events-dir "$events_dir" --report "$report"
