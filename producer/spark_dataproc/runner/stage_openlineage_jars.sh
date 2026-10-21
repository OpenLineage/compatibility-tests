#!/bin/bash

# Makes sure the OpenLineage spark and GCS transport jars of the given versions are in the shared GCS jar
# directory, and prints '<version>:<spark jar>:<gcs transport jar>' entries separated by semicolons,
# as expected by the OPENLINEAGE_JARS cluster metadata of get_openlineage_jar.sh.
#
# Released jars are downloaded from Maven and uploaded only when they are missing from the directory.
# With --snapshots the jars of the latest OpenLineage build are uploaded (replacing the previous build with
# the same snapshot version) and used for every version; a jar missing from the build falls back to the release.

set -euo pipefail

usage() {
  echo "Usage: $0 [--snapshots] [--jars-dir gs://...] <version>..." >&2
  exit 1
}

jars_dir="gs://open-lineage-e2e/jars"
snapshots=false
versions=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshots) snapshots=true; shift ;;
    --jars-dir) jars_dir="${2%/}"; shift 2 ;;
    -*) usage ;;
    *) versions+=("$1"); shift ;;
  esac
done
[[ ${#versions[@]} -gt 0 ]] || usage

readonly MAVEN_URL="https://repo1.maven.org/maven2/io/openlineage"
download_dir=$(mktemp -d)
trap 'rm -rf "$download_dir"' EXIT

# Prints the file name of the released jar, uploading it first when it is not in the jar directory.
release_jar() {
  local artifact="$1" version="$2"
  local file="$artifact-$version.jar"
  if gcloud storage ls "$jars_dir/$file" > /dev/null 2>&1; then
    echo "$file already in $jars_dir" >&2
  else
    echo "$file not in $jars_dir, downloading from Maven" >&2
    curl -fsSL -o "$download_dir/$file" "$MAVEN_URL/$artifact/$version/$file"
    gcloud storage cp "$download_dir/$file" "$jars_dir/$file" >&2
  fi
  echo "$file"
}

snapshot_spark=""
snapshot_gcs=""
if [[ "$snapshots" == "true" ]]; then
  mkdir -p "$download_dir/snapshots"
  python "$(dirname "$0")/../../../scripts/get_latest_unreleased_artifact.py" \
    --path="$download_dir/snapshots" \
    --skip-java=true --skip-flink=true --skip-sql=true --skip-extensions=true \
    --skip-gcp-lineage=true --skip-s3=true >&2
  snapshot_spark=$(cd "$download_dir/snapshots" && ls openlineage-spark_2.12-*.jar 2> /dev/null | head -n 1 || true)
  snapshot_gcs=$(cd "$download_dir/snapshots" && ls transports-gcs-*.jar 2> /dev/null | head -n 1 || true)
  for file in $snapshot_spark $snapshot_gcs; do
    gcloud storage cp "$download_dir/snapshots/$file" "$jars_dir/$file" >&2
  done
fi

entries=()
for version in "${versions[@]}"; do
  spark_jar="$snapshot_spark"
  [[ -n "$spark_jar" ]] || spark_jar=$(release_jar openlineage-spark_2.12 "$version")
  gcs_jar="$snapshot_gcs"
  [[ -n "$gcs_jar" ]] || gcs_jar=$(release_jar transports-gcs "$version")
  entries+=("$version:$spark_jar:$gcs_jar")
done

(IFS=';'; echo "${entries[*]}")
