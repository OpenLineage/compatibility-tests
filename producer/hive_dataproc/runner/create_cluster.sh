#!/bin/bash

# Creates the Dataproc cluster the Hive scenarios run on, for one Hive release: the image and Hive properties from
# runner/cluster.json, the OpenLineage hive jar and the GCS transport jar installed by dev/dataproc/install_jars.sh.
# Used by CI (producer_hive_dataproc.yml) and by run_hive_dataproc_tests.sh.

set -euo pipefail

HIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$HIVE_DIR/../.." && pwd)"
# shellcheck source=dev/defaults.env
source "$REPO_ROOT/dev/defaults.env"

# Temporary: released transports-gcs 1.40.0-1.55.0 break Hive on Dataproc (half-relocated Woodstox stops HiveServer2,
# the bundled Conscrypt native library aborts the Tez AM). This snapshot has both fixed. Once a release has the fix
# (1.56.0?), drop the default: CI passes the matching transport (get-ol-artifacts' gcs output) and
# run_hive_dataproc_tests.sh downloads it from Maven like the hive jar.
DEFAULT_GCS_TRANSPORT_JAR="gs://open-lineage-e2e/jars/transports-gcs-1.56.0-SNAPSHOT-conscrypt-fix.jar"

usage() {
  cat >&2 <<USAGE
Usage: $0 --hive-release V --cluster-name NAME --hive-jar gs://... [options]

  --hive-release V             Hive release, a key of runner/cluster.json (e.g. 3.1.3)
  --cluster-name NAME          cluster to create
  --hive-jar URL               gs:// URL of the openlineage-hive jar
  --gcs-transport-jar URL      gs:// URL of the transports-gcs jar (default: $DEFAULT_GCS_TRANSPORT_JAR)
  --project PROJECT            GCP project (default $GCP_PROJECT)
  --region REGION              region (default $GCP_REGION)
  --bucket BUCKET              bucket the init action is uploaded to (default $GCS_BUCKET)
  --credentials-file PATH      service account key (default: application default credentials)
USAGE
  exit "${1:-1}"
}

hive_release="" cluster_name="" hive_jar="" gcs_transport_jar="$DEFAULT_GCS_TRANSPORT_JAR" credentials_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hive-release) hive_release="$2"; shift 2 ;;
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --hive-jar) hive_jar="$2"; shift 2 ;;
    --gcs-transport-jar) gcs_transport_jar="$2"; shift 2 ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --bucket) GCS_BUCKET="$2"; shift 2 ;;
    --credentials-file) credentials_file="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$hive_release" && -n "$cluster_name" && -n "$hive_jar" ]] || usage

config=$(jq -e --arg v "$hive_release" '.[$v]' "$HIVE_DIR/runner/cluster.json") \
  || { echo "Hive $hive_release is not in $HIVE_DIR/runner/cluster.json" >&2; exit 1; }
image=$(jq -r '.image' <<< "$config")
properties=$(jq -r '.properties | to_entries | map("\(.key)=\(.value)") | join(",")' <<< "$config")

# a copy per cluster: concurrent runs don't overwrite each other's init action; only needed while the cluster starts
scripts_dir="gs://$GCS_BUCKET/scripts/$cluster_name"
trap 'gcloud storage rm -r "$scripts_dir" > /dev/null 2>&1 || true' EXIT
init_action=$("$REPO_ROOT/dev/dataproc/gcs_upload.sh" --force "$REPO_ROOT/dev/dataproc/install_jars.sh" "$scripts_dir")

args=(--cluster-name "$cluster_name" --image-version "$image" --properties "$properties"
      --metadata "JARS=$hive_jar;$gcs_transport_jar" --init-actions "$init_action"
      --project "$GCP_PROJECT" --region "$GCP_REGION")
[[ -n "$credentials_file" ]] && args+=(--credentials-file "$credentials_file")
"$REPO_ROOT/dev/dataproc/create_cluster.sh" "${args[@]}"
