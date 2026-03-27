#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="$(cd "$SCRIPT_DIR/../../../runner" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"
PRODUCER_OUTPUT_EVENTS_DIR="${1:-}"

DBT_POSTGRES_HOST="${DBT_POSTGRES_HOST:-localhost}"
DBT_POSTGRES_PORT="${DBT_POSTGRES_PORT:-5432}"
DBT_POSTGRES_USER="${DBT_POSTGRES_USER:-testuser}"
DBT_POSTGRES_DB="${DBT_POSTGRES_DB:-dbt_test}"

resolve_compose_command() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    return 1
  fi
}

postgres_is_ready() {
  python - "$DBT_POSTGRES_HOST" "$DBT_POSTGRES_PORT" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(1)
    sys.exit(0 if sock.connect_ex((host, port)) == 0 else 1)
PY
}

ensure_local_postgres() {
  if postgres_is_ready; then
    echo "Using existing Postgres instance at ${DBT_POSTGRES_HOST}:${DBT_POSTGRES_PORT}"
    return 0
  fi

  local compose_command
  compose_command="$(resolve_compose_command)" || {
    echo "Postgres is not reachable at ${DBT_POSTGRES_HOST}:${DBT_POSTGRES_PORT} and Docker Compose is unavailable" >&2
    return 1
  }

  echo "Starting local Postgres container with Docker Compose"
  $compose_command -f "$COMPOSE_FILE" up -d postgres

  for attempt in $(seq 1 30); do
    if $compose_command -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$DBT_POSTGRES_USER" -d "$DBT_POSTGRES_DB" >/dev/null 2>&1; then
      echo "Postgres is ready"
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for Postgres to become ready" >&2
  return 1
}

if [[ -z "$PRODUCER_OUTPUT_EVENTS_DIR" ]]; then
  echo "Usage: $0 <producer_output_events_dir>" >&2
  exit 1
fi

if [[ ! -d "$PRODUCER_OUTPUT_EVENTS_DIR" ]]; then
  echo "Output events directory '${PRODUCER_OUTPUT_EVENTS_DIR}' does not exist" >&2
  exit 1
fi

ensure_local_postgres

cd "$SCRIPT_DIR"

cat <<EOF > openlineage.yml
transport:
  type: file
  log_file_path: "${PRODUCER_OUTPUT_EVENTS_DIR}/events.jsonl"
  append: true
EOF

dbt-ol seed --project-dir="$RUNNER_DIR" --profiles-dir="$RUNNER_DIR" --target=postgres --no-version-check
dbt-ol run --project-dir="$RUNNER_DIR" --profiles-dir="$RUNNER_DIR" --target=postgres --no-version-check

EVENTS_FILE="${PRODUCER_OUTPUT_EVENTS_DIR}/events.jsonl"
if [[ ! -f "$EVENTS_FILE" ]]; then
  echo "Expected OpenLineage events file was not created: $EVENTS_FILE" >&2
  exit 1
fi

jq -c '.' "$EVENTS_FILE" | nl -w1 -s' ' | while read -r i line; do
  echo "$line" | jq '.' > "${PRODUCER_OUTPUT_EVENTS_DIR}/event-$i.json"
done
rm "$EVENTS_FILE"
