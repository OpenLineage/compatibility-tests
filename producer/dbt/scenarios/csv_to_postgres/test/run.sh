#!/bin/bash

PRODUCER_OUTPUT_EVENTS_DIR=$1

if [ -d "$PRODUCER_OUTPUT_EVENTS_DIR" ]; then
  cd "$(dirname "${BASH_SOURCE[0]}")" || exit

  cat <<EOF > openlineage.yml
transport:
  type: file
  log_file_path: "${PRODUCER_OUTPUT_EVENTS_DIR}/events.jsonl"
  append: true
EOF

  dbt-ol seed --project-dir="../../../runner" --profiles-dir="../../../runner" --target=postgres --no-version-check
  dbt-ol run --project-dir="../../../runner" --profiles-dir="../../../runner" --target=postgres --no-version-check

  jq -c '.' "${PRODUCER_OUTPUT_EVENTS_DIR}/events.jsonl" | nl -w1 -s' ' | while read -r i line; do
    echo "$line" | jq '.' > "${PRODUCER_OUTPUT_EVENTS_DIR}/event-$i.json"
  done
  rm "${PRODUCER_OUTPUT_EVENTS_DIR}/events.jsonl"

else
  echo "Output events directory '${PRODUCER_OUTPUT_EVENTS_DIR}' does not exist"
fi