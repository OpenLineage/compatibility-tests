#!/bin/bash

# Decides what the release check runs, based on what select_components.sh found new:
# - a new OpenLineage release runs every component version of every producer with it, and the consumer scenarios check
# - a new component release (dbt, Dataproc image) runs only the new component version, with all OpenLineage
#   versions of the matrix (versions.json plus the latest release)
# - consumers run only when something else runs
# With FORCE_ALL=true (manual runs) every producer runs its full matrix.
# Parts that produced no result in an earlier run (PENDING_FILE, see pending_runs.py) are added to the matrices, so they're
# retried until they pass. Matrices are cross products, so adding a pending pair can re-run a few extra pairs.
#
# Environment: LATEST_OL, OL_CHANGED, LATEST_DBT, DBT_CHANGED, DATAPROC_CHANGED_FAMILIES (JSON list), FORCE_ALL,
#              PENDING_FILE (default generated-files/pending_runs.json)

set -euo pipefail

: "${OL_CHANGED:=false}" "${DBT_CHANGED:=false}" "${DATAPROC_CHANGED_FAMILIES:=[]}" "${FORCE_ALL:=false}"
: "${PENDING_FILE:=generated-files/pending_runs.json}"

pending='[]'
[[ -f "$PENDING_FILE" ]] && pending=$(jq -c . "$PENDING_FILE")

# true when a part of the given component is pending
is_pending() {
  jq -e --arg c "$1" 'any(.[]; .component == $c)' <<< "$pending" > /dev/null
}

# Prints the matrix of a producer, or nothing if it shouldn't run.
# $1 - producer directory name, $2 - JSON list of its new component versions, $3 - latest component release if tracked
get_matrix() {
  local component="$1" changed_versions="$2" latest_component="${3:-}"
  local versions_file="producer/$component/versions.json"

  jq -c \
    --arg latest_ol "$LATEST_OL" \
    --arg latest_component "$latest_component" \
    --argjson ol_changed "$OL_CHANGED" \
    --argjson force_all "$FORCE_ALL" \
    --argjson changed "$changed_versions" \
    --argjson pending "$pending" \
    --arg component "$component" '
    def with_latest($v): if $v != "" and index($v) == null then . + [$v] else . end;
    def with_all($vs): reduce $vs[] as $v (.; with_latest($v));
    (.openlineage_versions | with_latest($latest_ol)) as $all_ol
    | (.component_version | with_latest($latest_component)) as $all_components
    | (if $force_all or ($ol_changed and ($changed | length) > 0) then
        {openlineage_versions: $all_ol, component_version: $all_components}
      elif $ol_changed then
        {openlineage_versions: [$latest_ol], component_version: $all_components}
      elif ($changed | length) > 0 then
        {openlineage_versions: $all_ol, component_version: $changed}
      else
        null
      end) as $matrix
    | [$pending[] | select(.component == $component)] as $retry
    | if ($retry | length) > 0 then
        ($matrix // {openlineage_versions: [], component_version: []})
        | .openlineage_versions |= with_all([$retry[].openlineage_version])
        | .component_version |= with_all([$retry[].component_version])
      elif $matrix == null then
        empty
      else
        $matrix
      end' "$versions_file"
}

# JSON list of the component versions whose Dataproc image family got a new image
dataproc_changed_versions() {
  jq -c --argjson families "$DATAPROC_CHANGED_FAMILIES" \
    '[to_entries[] | select(.value as $f | $families | index($f)) | .key]' "producer/$1/dataproc_images.json"
}

dbt_changed_versions='[]'
[[ "$DBT_CHANGED" == "true" ]] && dbt_changed_versions=$(jq -nc --arg v "$LATEST_DBT" '[$v]')

spark_matrix=$(get_matrix spark_dataproc "$(dataproc_changed_versions spark_dataproc)")
hive_matrix=$(get_matrix hive_dataproc "$(dataproc_changed_versions hive_dataproc)")
dbt_matrix=$(get_matrix dbt "$dbt_changed_versions" "${LATEST_DBT:-}")

any_producer=false
for matrix in "$spark_matrix" "$hive_matrix" "$dbt_matrix"; do
  [[ -n "$matrix" ]] && any_producer=true
done
run_scenarios=$([[ "$OL_CHANGED" == "true" || "$FORCE_ALL" == "true" ]] || is_pending scenarios && echo true || echo false)
any_run=$([[ "$any_producer" == "true" || "$run_scenarios" == "true" ]] || is_pending dataplex && echo true || echo false)

echo "spark_dataproc_matrix=$spark_matrix"
echo "hive_dataproc_matrix=$hive_matrix"
echo "dbt_matrix=$dbt_matrix"
echo "run_spark_dataproc=$([[ -n "$spark_matrix" ]] && echo true || echo false)"
echo "run_hive_dataproc=$([[ -n "$hive_matrix" ]] && echo true || echo false)"
echo "run_dbt=$([[ -n "$dbt_matrix" ]] && echo true || echo false)"
echo "run_scenarios=$run_scenarios"
echo "run_dataplex=$any_run"
echo "any_run=$any_run"
