#!/bin/bash

# Copies the OpenLineage spec (OpenLineage.json and the facet schemas) of each given tag into <dest-dir>/<tag>/,
# as expected by scripts/validate_ol_events.py --spec_base_dir. Used by the run_event_validation action and for
# validating events outside of a producer run.
#
# Usage: get_ol_specs.sh <tags separated by commas> <dest-dir> [openlineage-repo-dir]
# Without openlineage-repo-dir the OpenLineage repository is cloned (without file contents until checkout) into a
# temporary directory.

set -euo pipefail

usage() {
  echo "Usage: $0 <tag>[,<tag>...] <dest-dir> [openlineage-repo-dir]" >&2
  exit "${1:-1}"
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage 0
[[ $# -ge 2 && $# -le 3 ]] || usage

IFS=',' read -ra tags <<< "$1"
dest_base=$(mkdir -p "$2" && cd "$2" && pwd)
repo_dir="${3:-}"

if [[ -z "$repo_dir" ]]; then
  repo_dir=$(mktemp -d)
  trap 'rm -rf "$repo_dir"' EXIT
  git clone --quiet --filter=blob:none --no-checkout https://github.com/OpenLineage/OpenLineage.git "$repo_dir"
fi

cd "$repo_dir"
git fetch --tags --quiet
for tag in "${tags[@]}"; do
  echo "Checking out tag: $tag"
  if git checkout --quiet "$tag"; then
    dest_dir="$dest_base/$tag"
    if [[ -d "spec" || -d "integration/common/openlineage" ]]; then
      mkdir -p "$dest_dir"
      if [[ -d "spec" ]]; then
        find spec -path './website' -prune -o -type f \( -name '*Facet.json' -o -name 'OpenLineage.json' \) -exec cp {} "$dest_dir" \;
      fi
      if [[ -d "integration/common/src/openlineage" ]]; then
        find integration/common/src/openlineage -type f -iname '*facet.json' -exec cp {} "$dest_dir" \;
      fi
      echo "success"
    else
      echo "Neither spec nor integration/common/src/openlineage directory found in $tag"
    fi
  else
    echo "Tag $tag not found!"
  fi
done
