#!/bin/bash

set -e


OUT_DIR="${1:-./updated-compatibility-tables}"
DOCS_TARGET="docs/integrations/openlineage_compatibility"
VERSIONS_ROOT="versioned_docs"

#======================================== HELPERS ================================================

log() {
  echo "$@" >&2
}

copy_file() {
  local src="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
  log "Copied: $src to $dest"
}

write_stub() {
  local dest="$1"
  local title="$2"
  local position="$3"

  mkdir -p "$(dirname "$dest")"
  cat > "$dest" <<EOF
---
sidebar_position: $position
title: $title
---

_
EOF
  log "Stub created at: $dest"
}

create_compatibility_dir() {
  local version_path=$1
  target_dir="$version_path/integrations/openlineage_compatibility"
  log "ensure $target_dir exists"
  mkdir -p "$target_dir"

  log "ensure $target_dir/_category_.json exists"
  if [[ ! -f "$target_dir/_category_.json" ]]; then
    cat > "$target_dir/_category_.json" <<EOF
{
  "label": "Openlineage Compatibility",
  "position": 99
}
EOF
  log "$target_dir/_category_.json created"
  fi
}

update_component_docs() {
  find "$OUT_DIR" -maxdepth 1 -name "*.md" | while read -r file; do
    base=$(basename "$file")
    copy_file "$file" "$DOCS_TARGET/$base"
  done


  for dir in "$OUT_DIR"/*/; do
    component=$(basename "$dir")
    if [[ "$component" != "openlineage_versions" ]]; then
      target="$DOCS_TARGET/$component"
      rm -rf "$target"
      cp -r "$dir" "$target"
      log "Copied versioned component directory: $component"
    fi
  done
}

copy_summary() {
  local src_dir=$1
  local target_base=$2
  local version=$3
  local summary_type=$4
  local latest_version=$5

  target_dir="$target_base/integrations/openlineage_compatibility"
  src="$src_dir/${summary_type}_summary.md"

  if [[ -f "$src" ]]; then
    copy_file "$src" "$target_dir/${summary_type}_summary.md"
    echo "$version"
  else
    echo "$latest_version"
  fi
}

stub_missing_summaries() {
  target_dir=$1
  [[ -f "$target_dir/consumer_summary.md" ]] || write_stub "$target_dir/consumer_summary.md" "Consumer Summary" 1
  [[ -f "$target_dir/producer_summary.md" ]] || write_stub "$target_dir/producer_summary.md" "Producer Summary" 2
}

create_md_file_proxies(){
  local src_dir=$1
  local dest_dir=$2

  find "$src_dir" -maxdepth 1 -name "*.md" | while read -r md_file; do
    file_name=$(basename "$md_file")
    log "created proxy for $md_file"
    head -n 4 "$md_file" > "$dest_dir/$file_name"
    echo -e "\nimport Transports from '@site/$src_dir/$file_name';\n\n<Transports/>\n" >> "$dest_dir/$file_name"
  done
}

#======================================== MAIN ================================================
log ""
log "Ensure that all openlineage_compatibility directories exist"
log ""

create_compatibility_dir "docs"
for version_path in "$VERSIONS_ROOT"/version-*; do
  create_compatibility_dir "$version_path"
done

log ""
log "Update component docs with latest test results"
log ""

update_component_docs

log ""
log "Copy generated summaries to appropriate locations"
log ""

latest_consumer_version=""
latest_producer_version=""

for src_dir in "$OUT_DIR/openlineage_versions/"*/; do
  version=$(basename "$src_dir")
  target_base="$VERSIONS_ROOT/version-$version"
  latest_consumer_version=$(copy_summary "$src_dir" "$target_base" "$version" "consumer" "$latest_consumer_version")
  latest_producer_version=$(copy_summary "$src_dir" "$target_base" "$version" "producer" "$latest_producer_version")
done

# Copy the latest versioned producer/consumer summary to docs
copy_summary "$VERSIONS_ROOT/version-$latest_consumer_version/integrations/openlineage_compatibility" \
  "docs" "$latest_consumer_version" "consumer" "$latest_consumer_version"

copy_summary "$VERSIONS_ROOT/version-$latest_consumer_version/integrations/openlineage_compatibility" \
  "docs" "$latest_producer_version" "producer" "$latest_producer_version"



# Handle versioned_docs that have no generated summary at all
log ""
log "Ensuring all versioned_docs have summary files..."
log ""

for version_path in "$VERSIONS_ROOT"/version-*; do
  stub_missing_summaries "$version_path/integrations/openlineage_compatibility"
done
stub_missing_summaries "docs/integrations/openlineage_compatibility"



log ""
log "Replicating component structure inside versioned_docs..."
log ""

for version_path in "$VERSIONS_ROOT"/version-*; do
  target_base="$version_path/integrations/openlineage_compatibility"
  src_base="docs/integrations/openlineage_compatibility"
  create_md_file_proxies $src_base $target_base
  # Versioned components
  for comp_dir in "$src_base"/*/; do
    if [[ -f "$comp_dir/_category_.json" ]]; then
      dest_dir="${comp_dir/docs/$version_path}"
      mkdir -p "$dest_dir"
      cp "$comp_dir/_category_.json" "$dest_dir/_category_.json"
      # Proxy each .md file in the component directory
      create_md_file_proxies "$comp_dir" "$dest_dir"
    fi
  done

done

log ""
log "Success."