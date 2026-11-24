#!/bin/bash

# Uploads a local file into a GCS directory unless a file with that name is already there, and prints its gs:// URL.
# --force uploads anyway (for files that change between runs, e.g. init actions; give those a per-run directory).

set -euo pipefail

usage() {
  echo "Usage: $0 [--force] <local-file> <gs://bucket/dir>" >&2
  exit "${1:-1}"
}

force=false
positional=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) force=true; shift ;;
    -h|--help) usage 0 ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *) positional+=("$1"); shift ;;
  esac
done
[[ ${#positional[@]} -eq 2 ]] || usage
local_file="${positional[0]}"
target="${positional[1]%/}/$(basename "$local_file")"
[[ -f "$local_file" ]] || { echo "No such file: $local_file" >&2; exit 1; }

if [[ "$force" == "true" ]] || ! gcloud storage ls "$target" > /dev/null 2>&1; then
  gcloud storage cp "$local_file" "$target" >&2
else
  echo "$target already exists, not uploading" >&2
fi
echo "$target"
