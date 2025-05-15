#!/bin/bash

set -e

# Usage: ./deploy_docs.sh [output_dir] [--dry-run]
OUT_DIR="${1:-./out}"
DOCS_TARGET="docs/integrations/openlineage_compatibility"
VERSIONS_ROOT="versioned_docs"
DRY_RUN=false

# Detect dry-run
if [[ "$2" == "--dry-run" ]] || [[ "$1" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "Running in DRY RUN mode — no files will be written."
fi

log() {
  echo "$@"
}

copy_file() {
  local src="$1"
  local dest="$2"
  if $DRY_RUN; then
    log "Would copy: $src → $dest"
  else
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
    log "Copied: $src → $dest"
  fi
}

write_stub() {
  local dest="$1"
  local title="$2"
  local position="$3"
  if $DRY_RUN; then
    log "Would create stub: $dest"
  else
    mkdir -p "$(dirname "$dest")"
    cat > "$dest" <<EOF
---
sidebar_position: $position
title: $title
---

_
EOF
    log "Stub created at: $dest"
  fi
}

log ""
log "Syncing component docs..."

mkdir -p "$DOCS_TARGET"

# Copy versioned components md files
find "$OUT_DIR" -maxdepth 1 -name "*.md" | while read -r file; do
  base=$(basename "$file")
  copy_file "$file" "$DOCS_TARGET/$base"
done

# Copy versioned component subdirectories with category + versioned .mds
for dir in "$OUT_DIR"/*/; do
  component=$(basename "$dir")
  if [[ "$component" != "openlineage_versions" ]]; then
    target="$DOCS_TARGET/$component"
    if $DRY_RUN; then
      log "Would copy versioned component: $component"
    else
      rm -rf "$target"
      cp -r "$dir" "$target"
      log "Copied versioned component directory: $component"
    fi
  fi
done

log ""
log "Syncing OpenLineage summaries to versioned_docs..."

log ""
log "Copying latest generated summaries to docs/..."

if [[ -n "$latest_consumer_version" ]]; then
  src="$OUT_DIR/openlineage_versions/$latest_consumer_version/consumer_summary.md"
  dest="$DOCS_TARGET/consumer_summary.md"
  copy_file "$src" "$dest"
else
  log "No latest consumer summary found"
fi

if [[ -n "$latest_producer_version" ]]; then
  src="$OUT_DIR/openlineage_versions/$latest_producer_version/producer_summary.md"
  dest="$DOCS_TARGET/producer_summary.md"
  copy_file "$src" "$dest"
else
  log "No latest producer summary found"
fi



log ""
log "Ensuring all versioned_docs have required directories and category files"

for version_path in "$VERSIONS_ROOT"/version-*; do
  [[ -d "$version_path" ]] || continue
  target_dir="$version_path/integrations/openlineage_compatibility"
  mkdir -p "$target_dir"

  if [[ ! -f "$target_dir/_category_.json" ]]; then
    cat > "$target_dir/_category_.json" <<EOF
{
  "label": "Openlineage Compatibility",
  "position": 99
}
EOF
  fi

done

# Handle versioned_docs that have no generated summary at all
log ""
log "Ensuring all versioned_docs have summary files..."

for version_path in "$VERSIONS_ROOT"/version-*; do
  [[ -d "$version_path" ]] || continue
  version=$(basename "$version_path" | sed 's/^version-//')
  source_dir="$OUT_DIR/openlineage_versions/$version"
  target_dir="$version_path/integrations/openlineage_compatibility"
  mkdir -p "$target_dir"


  # If summary files were not already written, create stubs
  if [[ ! -f "$source_dir/consumer_summary.md" ]]; then
    write_stub "$target_dir/consumer_summary.md" "Consumer Summary" 1
  fi
  if [[ ! -f "$source_dir/producer_summary.md" ]]; then
    write_stub "$target_dir/producer_summary.md" "Producer Summary" 2
  fi
done

log ""
log "Replicating component structure inside versioned_docs..."

for version_path in "$VERSIONS_ROOT"/version-*; do
  [[ -d "$version_path" ]] || continue
  version=$(basename "$version_path" | sed 's/^version-//')
  target_base="$version_path/integrations/openlineage_compatibility"

  # Versioned components
  for comp_dir in "$OUT_DIR"/*/; do
    comp=$(basename "$comp_dir")
    category_file="$comp_dir/_category_.json"

    # Copy _category_.json for this component if it exists
    if [[ -f "$category_file" ]]; then
      dest_dir="$target_base/$comp"
      dest_category="$dest_dir/_category_.json"

      if $DRY_RUN; then
        log "Would copy _category_.json for $comp → $dest_category"
      else
        mkdir -p "$dest_dir"
        cp "$category_file" "$dest_category"
        log "Copied _category_.json for $comp"
      fi
    fi

    # Proxy each .md file in the component directory
    find "$comp_dir" -maxdepth 1 -name "*.md" | while read -r md_file; do
      version_file=$(basename "$md_file")
      version="${version_file%.md}"
      dest_dir="$target_base/$comp"
      dest_file="$dest_dir/$version.md"

      if $DRY_RUN; then
        log "Would proxy versioned component: $md_file → $dest_file"
      else
        mkdir -p "$dest_dir"
        head -n 4 "$md_file" > "$dest_file"
        echo -e "\nimport Transports from '@site/docs/integrations/openlineage_compatibility/$comp/$version.md';\n\n<Transports/>\n" >> "$dest_file"
        log "Proxy created for $comp/$version"
      fi
    done
  done
done


log ""
log "Success."