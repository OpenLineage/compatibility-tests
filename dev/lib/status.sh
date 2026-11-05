# Sourced by the producer run scripts. status.json records how each scenario's producer job ended, in the format the
# Spark runner writes and validate_ol_events.py --run_status reads: [{"scenario": ..., "state": ..., "job_id": ...}].
# A state other than DONE fails the scenario in validation.

# status_init <status.json>
status_init() {
  mkdir -p "$(dirname "$1")"
  echo '[]' > "$1"
}

# record_status <status.json> <scenario> <state> [job_id]
record_status() {
  local file="$1" scenario="$2" state="$3" job_id="${4:-}"
  jq --arg scenario "$scenario" --arg state "$state" --arg job_id "$job_id" \
    '. + [{scenario: $scenario, state: $state, job_id: $job_id}]' "$file" > "$file.tmp"
  mv "$file.tmp" "$file"
}
