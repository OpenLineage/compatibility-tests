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
# a stuck Docker engine makes docker commands wait forever; give up after these many seconds
DOCKER_CHECK_TIMEOUT="${DOCKER_CHECK_TIMEOUT:-30}"
DOCKER_UP_TIMEOUT="${DOCKER_UP_TIMEOUT:-300}"  # includes pulling the image the first time

# run_with_timeout SECONDS CMD...: CMD's exit code, or 124 after stopping it (macOS has no `timeout`)
run_with_timeout() {
  local seconds=$1 waited=0
  shift
  "$@" &
  local pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    if (( waited >= seconds )); then
      kill -TERM "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "$pid"
}

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

  if ! run_with_timeout "$DOCKER_CHECK_TIMEOUT" docker info >/dev/null 2>&1; then
    echo "The Docker engine didn't answer within ${DOCKER_CHECK_TIMEOUT}s: start (or restart) Docker, or point" \
      "DBT_POSTGRES_HOST/DBT_POSTGRES_PORT at a running Postgres" >&2
    return 1
  fi

  echo "Starting local Postgres container with Docker Compose"
  # shellcheck disable=SC2086  # compose_command is "docker compose" or "docker-compose"
  if ! run_with_timeout "$DOCKER_UP_TIMEOUT" $compose_command -f "$COMPOSE_FILE" up -d postgres; then
    echo "Starting Postgres with Docker Compose failed or took more than ${DOCKER_UP_TIMEOUT}s" >&2
    return 1
  fi

  for _ in $(seq 1 30); do
    # shellcheck disable=SC2086
    if run_with_timeout 10 $compose_command -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$DBT_POSTGRES_USER" -d "$DBT_POSTGRES_DB" >/dev/null 2>&1; then
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
dbt-ol test --project-dir="$RUNNER_DIR" --profiles-dir="$RUNNER_DIR" --target=postgres --no-version-check

EVENTS_FILE="${PRODUCER_OUTPUT_EVENTS_DIR}/events.jsonl"
if [[ ! -f "$EVENTS_FILE" ]]; then
  echo "Expected OpenLineage events file was not created: $EVENTS_FILE" >&2
  exit 1
fi

jq -c '.' "$EVENTS_FILE" | nl -w1 -s' ' | while read -r i line; do
  echo "$line" | jq '.' > "${PRODUCER_OUTPUT_EVENTS_DIR}/event-$i.json"
done
rm "$EVENTS_FILE"
