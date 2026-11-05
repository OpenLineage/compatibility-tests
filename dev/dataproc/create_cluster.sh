#!/bin/bash

# Creates a Dataproc cluster with dev/dataproc/dataproc_workflow.py. Producer-specific settings (image, metadata,
# properties, init actions) come from the producer's runner/create_cluster.sh. Credentials: --credentials-file, or
# GOOGLE_APPLICATION_CREDENTIALS / the application default credentials (gcloud auth application-default login).

set -euo pipefail

DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=dev/defaults.env
source "$DEV_DIR/defaults.env"

usage() {
  cat >&2 <<USAGE
Usage: $0 --cluster-name NAME --image-version VERSION [options]

  --cluster-name NAME           cluster to create (required)
  --image-version VERSION       Dataproc image version, e.g. 2.2-ubuntu22 (required)
  --metadata K=V,...            cluster metadata
  --properties P=V,...          cluster properties, e.g. hive:hive.conf.validation=false
  --init-actions gs://...,...   initialization actions
  --master-machine-type TYPE    master machine type (default n1-standard-2)
  --project PROJECT             GCP project (default $GCP_PROJECT)
  --region REGION               region (default $GCP_REGION)
  --credentials-file PATH       service account key (default: application default credentials)
USAGE
  exit "${1:-1}"
}

cluster_name="" image_version="" metadata="" properties="" init_actions="" master_machine_type="" credentials_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --image-version) image_version="$2"; shift 2 ;;
    --metadata) metadata="$2"; shift 2 ;;
    --properties) properties="$2"; shift 2 ;;
    --init-actions) init_actions="$2"; shift 2 ;;
    --master-machine-type) master_machine_type="$2"; shift 2 ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --credentials-file) credentials_file="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$cluster_name" && -n "$image_version" ]] || usage

args=(--project-id "$GCP_PROJECT" --region "$GCP_REGION" --cluster-name "$cluster_name" --dataproc-image-version "$image_version")
[[ -n "$metadata" ]] && args+=(--metadata "$metadata")
[[ -n "$properties" ]] && args+=(--cluster-properties "$properties")
[[ -n "$init_actions" ]] && args+=(--initialization-actions "$init_actions")
[[ -n "$master_machine_type" ]] && args+=(--master-machine-type "$master_machine_type")
[[ -n "$credentials_file" ]] && args+=(--credentials-file "$credentials_file")

python "$DEV_DIR/dataproc/dataproc_workflow.py" create-cluster "${args[@]}"
