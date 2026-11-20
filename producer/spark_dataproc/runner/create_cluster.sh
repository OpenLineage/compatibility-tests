#!/bin/bash

# Creates the Dataproc cluster the Spark scenarios run on, for one Spark release: the image, connectors and other jars
# from runner/cluster.json, installed by dev/dataproc/install_jars.sh, plus the OpenLineage spark jar of every given
# version in /opt/openlineage/<version>/ on the master (a job picks one with spark.driver.extraClassPath).
# Used by CI (producer_spark_dataproc.yml) and by run_spark_dataproc_tests.sh.

set -euo pipefail

SPARK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SPARK_DIR/../.." && pwd)"
CLUSTER_JSON="$SPARK_DIR/runner/cluster.json"
OPENLINEAGE_DIR=/opt/openlineage
# shellcheck source=dev/defaults.env
source "$REPO_ROOT/dev/defaults.env"

usage() {
  cat >&2 <<USAGE
Usage: $0 --spark-release V --cluster-name NAME --openlineage-jars 'v:spark jar:gcs jar;...' [options]

  --spark-release V            Spark release, a key of "releases" in runner/cluster.json (e.g. 3.5.1)
  --cluster-name NAME          cluster to create
  --openlineage-jars LIST      as printed by runner/stage_openlineage_jars.sh; the jars are in gs://<bucket>/jars
  --project PROJECT            GCP project (default $GCP_PROJECT)
  --region REGION              region (default $GCP_REGION)
  --bucket BUCKET              bucket with the jars, and where the init actions are uploaded (default $GCS_BUCKET)
  --credentials-file PATH      service account key (default: application default credentials)
USAGE
  exit "${1:-1}"
}

spark_release="" cluster_name="" openlineage_jars="" credentials_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --spark-release) spark_release="$2"; shift 2 ;;
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --openlineage-jars) openlineage_jars="$2"; shift 2 ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --bucket) GCS_BUCKET="$2"; shift 2 ;;
    --credentials-file) credentials_file="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$spark_release" && -n "$cluster_name" && -n "$openlineage_jars" ]] || usage

release=$(jq -e --arg v "$spark_release" '.releases[$v]' "$CLUSTER_JSON") \
  || { echo "Spark $spark_release is not in $CLUSTER_JSON" >&2; exit 1; }
image=$(jq -r '.image' <<< "$release")
jars_dir="gs://$GCS_BUCKET/jars"

# the BigQuery connector of the Spark release, staged from Maven Central the first time
connector_version=$(jq -r '.bigquery_connector_version' "$CLUSTER_JSON")
spark_short=$(jq -r '.spark_short' <<< "$release")
bq_jar="spark-$spark_short-bigquery-$connector_version.jar"
if ! gcloud storage ls "$jars_dir/$bq_jar" > /dev/null 2>&1; then
  download_dir=$(mktemp -d)
  curl -fsSL -o "$download_dir/$bq_jar" \
    "https://repo1.maven.org/maven2/com/google/cloud/spark/spark-$spark_short-bigquery/$connector_version/$bq_jar"
  "$REPO_ROOT/dev/dataproc/gcs_upload.sh" "$download_dir/$bq_jar" "$jars_dir" > /dev/null
  rm -rf "$download_dir"
fi

# every node: the connector, the common jars and the release's own jars
jars="$jars_dir/$bq_jar"
while read -r jar; do
  jars+=";$jar"
done < <(jq -r --arg v "$spark_release" '.common_jars[], .releases[$v].jars[]' "$CLUSTER_JSON")

# master only: each OpenLineage version's spark jar in its own directory
master_jars=""
IFS=';' read -ra entries <<< "$openlineage_jars"
for entry in "${entries[@]}"; do
  IFS=':' read -r version spark_jar _ <<< "$entry"
  [[ -n "$version" && -n "$spark_jar" ]] || { echo "Bad --openlineage-jars entry: '$entry'" >&2; exit 1; }
  master_jars+="${master_jars:+;}$OPENLINEAGE_DIR/$version=$jars_dir/$spark_jar"
done

# SPARK_BQ_CONNECTOR_URL: Dataproc 2.1+ images replace their built-in BigQuery connector with this one; without it the
# built-in connector stays next to ours ("Multiple sources found for bigquery"). 2.0 images have none, hence also in JARS.
metadata="SPARK_BQ_CONNECTOR_URL=$jars_dir/$bq_jar"
metadata+=",JARS=$jars,JARS_TARGET_DIR=/usr/lib/spark/jars,MASTER_JARS=$master_jars"
metadata+=$(jq -r '.metadata | to_entries | map(",\(.key)=\(.value)") | join("")' "$CLUSTER_JSON")

# a copy per cluster, so concurrent runs don't swap each other's init actions; only needed while the cluster starts
scripts_dir="gs://$GCS_BUCKET/scripts/$cluster_name"
trap 'gcloud storage rm -r "$scripts_dir" > /dev/null 2>&1 || true' EXIT
init_actions=""
for script in "$REPO_ROOT/dev/dataproc/install_jars.sh" "$SPARK_DIR/runner/cloud_sql_proxy.sh"; do
  init_actions+="${init_actions:+,}$("$REPO_ROOT/dev/dataproc/gcs_upload.sh" --force "$script" "$scripts_dir")"
done

args=(--cluster-name "$cluster_name" --image-version "$image" --metadata "$metadata" --init-actions "$init_actions"
      --master-machine-type "$(jq -r '.master_machine_type' "$CLUSTER_JSON")" --project "$GCP_PROJECT" --region "$GCP_REGION")
[[ -n "$credentials_file" ]] && args+=(--credentials-file "$credentials_file")
"$REPO_ROOT/dev/dataproc/create_cluster.sh" "${args[@]}"
