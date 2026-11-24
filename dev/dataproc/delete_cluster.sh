#!/bin/bash

# Deletes a Dataproc cluster, or lists the clusters whose name contains your user name (leftovers of local runs).

set -euo pipefail

DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=dev/defaults.env
source "$DEV_DIR/defaults.env"

usage() {
  cat >&2 <<USAGE
Usage: $0 --cluster-name NAME [options]
       $0 --list-mine [options]

  --cluster-name NAME       cluster to delete
  --list-mine               list clusters whose name contains "$(user_slug)" instead
  --project PROJECT         GCP project (default $GCP_PROJECT)
  --region REGION           region (default $GCP_REGION)
  --credentials-file PATH   service account key (default: application default credentials)
USAGE
  exit "${1:-1}"
}

# user name as it appears in cluster names (lowercase letters, digits and dashes)
user_slug() {
  echo "${USER:-user}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '-'
}

cluster_name="" list_mine=false credentials_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --list-mine) list_mine=true; shift ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --credentials-file) credentials_file="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ "$list_mine" == "true" ]]; then
  gcloud dataproc clusters list --project "$GCP_PROJECT" --region "$GCP_REGION" \
    --filter="clusterName~$(user_slug)" --format="table(clusterName,status.state,status.stateStartTime)"
  exit 0
fi
[[ -n "$cluster_name" ]] || usage

args=(--project-id "$GCP_PROJECT" --region "$GCP_REGION" --cluster-name "$cluster_name")
[[ -n "$credentials_file" ]] && args+=(--credentials-file "$credentials_file")
python "$DEV_DIR/dataproc/dataproc_workflow.py" terminate-cluster "${args[@]}"
