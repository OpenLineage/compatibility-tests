#!/bin/bash

# Runs the Hive scenarios for one Hive version x OpenLineage version on a Dataproc cluster, the way CI does
# (.github/workflows/producer_hive_dataproc.yml), and validates the events. See "Run locally, as CI does" in README.md.
#
#   1. a virtualenv with dev/dataproc/requirements.txt (cached, reused by later runs)
#   2. the scenarios valid for the versions (scripts/get_valid_test_scenarios.sh), or the ones given with --scenarios
#   3. the openlineage-hive jar from Maven Central, uploaded to gs://<bucket>/jars (skipped when already there)
#   4. runner/create_cluster.sh: a cluster named after you; deleted at the end, also when a step fails
#   5. runner/run_scenarios.sh: runs the scenarios, downloads the events, writes status.json
#   6. dev/validation/validate_locally.sh: validates the events, writes the report, exits 1 if a scenario failed

set -euo pipefail

HIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HIVE_DIR/../.." && pwd)"
CACHE_DIR="${OL_COMPAT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/openlineage-compatibility-tests}"
# shellcheck source=dev/defaults.env
source "$REPO_ROOT/dev/defaults.env"

usage() {
  cat >&2 <<USAGE
Usage: $0 --component-version V --openlineage-version OL [options]

  --component-version V        Hive version, a key of runner/cluster.json (e.g. 3.1.3)
  --openlineage-version OL     OpenLineage release, e.g. 1.55.0
  --scenarios 's1;s2'          scenarios to run (default: every scenario valid for the versions)
  --hive-jar PATH|gs://...     openlineage-hive jar to test instead of the release from Maven (e.g. a local build)
  --cluster-name NAME          run on this existing cluster; it isn't created or deleted
  --keep-cluster               don't delete the cluster at the end (delete it later with dev/dataproc/delete_cluster.sh)
  --events-dir DIR             where events and status.json go (default: ./hive-dataproc-events-<V>-<OL>)
  --report-dir DIR             where the report goes (default: .); named hive-dataproc-<V>-<OL>-report.json like the CI artifact
  --project PROJECT            GCP project (default $GCP_PROJECT)
  --region REGION              region (default $GCP_REGION)
  --bucket BUCKET              bucket for jars, the init action and events (default $GCS_BUCKET)

Credentials: the application default credentials (gcloud auth application-default login) and the gcloud CLI login.
Environment: PYTHON (default python3) creates the virtualenv; OL_COMPAT_CACHE moves the cache
(default ~/.cache/openlineage-compatibility-tests).
USAGE
  exit "${1:-1}"
}

component_version="" ol_version="" scenarios="" hive_jar="" cluster_name="" keep_cluster=false events_dir="" report_dir="."
while [[ $# -gt 0 ]]; do
  case "$1" in
    --component-version) component_version="$2"; shift 2 ;;
    --openlineage-version) ol_version="$2"; shift 2 ;;
    --scenarios) scenarios="$2"; shift 2 ;;
    --hive-jar) hive_jar="$2"; shift 2 ;;
    --cluster-name) cluster_name="$2"; shift 2 ;;
    --keep-cluster) keep_cluster=true; shift ;;
    --events-dir) events_dir="$2"; shift 2 ;;
    --report-dir) report_dir="$2"; shift 2 ;;
    --project) GCP_PROJECT="$2"; shift 2 ;;
    --region) GCP_REGION="$2"; shift 2 ;;
    --bucket) GCS_BUCKET="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done
[[ -n "$component_version" && -n "$ol_version" ]] || usage
events_dir="${events_dir:-$PWD/hive-dataproc-events-$component_version-$ol_version}"
mkdir -p "$report_dir"
report="$(cd "$report_dir" && pwd)/hive-dataproc-$component_version-$ol_version-report.json"
gcp=(--project "$GCP_PROJECT" --region "$GCP_REGION" --bucket "$GCS_BUCKET")

echo "== 1. Dataproc client"
venv="$CACHE_DIR/venvs/dataproc"
requirements_hash=$(shasum "$REPO_ROOT/dev/dataproc/requirements.txt" | cut -d' ' -f1)
if [[ ! -x "$venv/bin/python" || "$(cat "$venv/.requirements-hash" 2> /dev/null)" != "$requirements_hash" ]]; then
  rm -rf "$venv"
  "${PYTHON:-python3}" -m venv "$venv"
  "$venv/bin/python" -m pip install --quiet --upgrade pip
  "$venv/bin/python" -m pip install --quiet -r "$REPO_ROOT/dev/dataproc/requirements.txt"
  echo "$requirements_hash" > "$venv/.requirements-hash"
fi
export PATH="$venv/bin:$PATH"  # the dev/ and runner/ scripts call `python`
echo "virtualenv: $venv"

echo "== 2. Scenarios"
if [[ -z "$scenarios" ]]; then
  scenarios=$("$REPO_ROOT/scripts/get_valid_test_scenarios.sh" "$HIVE_DIR/scenarios" "$component_version" "$ol_version")
  [[ -n "$scenarios" ]] || { echo "No scenario is valid for Hive $component_version and OpenLineage $ol_version" >&2; exit 1; }
fi
echo "$scenarios"

if [[ -n "$cluster_name" ]]; then
  echo "== 3-4. Using the existing cluster $cluster_name"
else
  echo "== 3. openlineage-hive jar"
  if [[ -z "$hive_jar" ]]; then
    # the release: the same file CI uploads, so an upload from an earlier run (or CI) is reused
    jar="$CACHE_DIR/jars/openlineage-hive-$ol_version.jar"
    if [[ ! -s "$jar" ]]; then
      mkdir -p "$(dirname "$jar")"
      curl -fsSL -o "$jar.part" \
        "https://repo1.maven.org/maven2/io/openlineage/openlineage-hive/$ol_version/openlineage-hive-$ol_version.jar"
      mv "$jar.part" "$jar"
    fi
    hive_jar=$("$REPO_ROOT/dev/dataproc/gcs_upload.sh" "$jar" "gs://$GCS_BUCKET/jars")
  elif [[ "$hive_jar" != gs://* ]]; then
    # a local build: a directory per content, so it never reuses (or replaces) another jar with the same name
    hive_jar=$("$REPO_ROOT/dev/dataproc/gcs_upload.sh" "$hive_jar" \
      "gs://$GCS_BUCKET/jars/local/$(shasum "$hive_jar" | cut -c1-12)")
  fi
  echo "$hive_jar"

  echo "== 4. Cluster"
  user_slug=$(echo "${USER:-user}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '-' | cut -c1-15)
  cluster_name="hive-${user_slug}-${component_version//./}-${ol_version//./}-$(date +%s)"
  if [[ "$keep_cluster" == "true" ]]; then
    echo "The cluster is kept; delete it with: dev/dataproc/delete_cluster.sh --cluster-name $cluster_name"
  else
    # shellcheck disable=SC2064  # expand now: the names are fixed from here on
    trap "'$REPO_ROOT/dev/dataproc/delete_cluster.sh' --cluster-name '$cluster_name' --project '$GCP_PROJECT' --region '$GCP_REGION'" EXIT
  fi
  "$HIVE_DIR/runner/create_cluster.sh" --hive-release "$component_version" --cluster-name "$cluster_name" \
    --hive-jar "$hive_jar" "${gcp[@]}"
fi

echo "== 5. Run"
"$HIVE_DIR/runner/run_scenarios.sh" --cluster-name "$cluster_name" --scenarios "$scenarios" --events-dir "$events_dir" "${gcp[@]}"

echo "== 6. Validate"
"$REPO_ROOT/dev/validation/validate_locally.sh" --component hive_dataproc --component-version "$component_version" \
  --openlineage-version "$ol_version" --events-dir "$events_dir" --report "$report"
