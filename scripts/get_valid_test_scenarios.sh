#!/bin/bash

# Ensure arguments are provided
if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <scenario_path> <component_version> <openlineage_version>"
  exit 1
fi

scenario_path="$1"
component_version="$2"
openlineage_version="$3"

version_check() {
  local min max version
  read -r min max < <(jq -r "$1.min // \"0.0.0\" , $1.max // \"999.999.999\"" "$2" | xargs)
    IFS='.' read -r v1 v2 v3 <<< "$3"; version=$(( v1 * 1000000 + v2 * 1000 + v3 ))
  IFS='.' read -r m1 m2 m3 <<< "$min"; min=$(( m1 * 1000000 + m2 * 1000 + m3 ))
  IFS='.' read -r M1 M2 M3 <<< "$max"; max=$(( M1 * 1000000 + M2 * 1000 + M3 ))
  [[ $version -ge $min && $version -le $max ]]
}

valid_scenarios=""
for dir in "$scenario_path"/*; do
    config_file="${dir}/config.json"
    [[ ! -f "$config_file" ]] && echo "NO CONFIG FILE FOR SCENARIO ${dir##*/}" && exit 1

    if version_check ".component_versions" "$config_file" "$component_version" &&
       version_check ".openlineage_versions" "$config_file" "$openlineage_version"; then
        valid_scenarios+=";${dir##*/}"
    fi
done

echo "${valid_scenarios/#;/}"
