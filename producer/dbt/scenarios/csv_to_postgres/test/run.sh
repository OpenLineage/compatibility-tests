#!/bin/bash

PRODUCER_OUTPUT_EVENTS_DIR=$1

if [ -d "$PRODUCER_OUTPUT_EVENTS_DIR" ]; then
  cd "$(dirname "${BASH_SOURCE[0]}")" || exit

  cat <<EOF > openlineage.yml
transport:
  type: file
  log_file_path: "${PRODUCER_OUTPUT_EVENTS_DIR}/openlineage_event"
  append: false
EOF

  dbt-ol seed --project-dir="../../../runner" --profiles-dir="../../../runner" --target=postgres --no-version-check
  dbt-ol run --project-dir="../../../runner" --profiles-dir="../../../runner" --target=postgres --no-version-check
else
  echo "Output events directory '${PRODUCER_OUTPUT_EVENTS_DIR}' does not exist"
fi