# assuming the version will not exceed 1000 this is the quickest way to get comparable values
version_sum() {
  IFS='.' read -r var1 var2 var3 <<< "$1"
  echo $(( var1 * 1000000 + var2 * 1000 + var3))
}

update_version() {
  local name="$1"
  local new_version="$2"

  jq --arg name "$name" \
     --arg version "$new_version" \
        'map(if .name == $name then .latest_version = $version else . end)' \
        generated-files/updated-releases.json > /tmp/releases.json \
  && mv /tmp/releases.json generated-files/updated-releases.json
}

ol_version() {
  current_ol=$(jq -r '.[] | select(.name | contains("openlineage")) | .latest_version ' generated-files/releases.json)
  latest_ol=$(curl https://api.github.com/repos/OpenLineage/OpenLineage/releases/latest -s | jq .tag_name -r)

  if (( $(version_sum $latest_ol) > $(version_sum $current_ol) )); then
    update_version "openlineage" "$latest_ol"
    echo "ol_release=${latest_ol}" >> $GITHUB_OUTPUT
    return 0
  fi
  echo "ol_release=${current_ol}" >> $GITHUB_OUTPUT
  return 1
}

dbt_version() {
  current_dbt=$(jq -r '.[] | select(.name | contains("dbt")) | .latest_version ' generated-files/releases.json)
  latest_dbt=$(pip index versions dbt-core | grep LATEST | awk '{print $2}')

  if (( $(version_sum $latest_dbt) > $(version_sum $current_dbt) )); then
    update_version "dbt" "$latest_dbt"
    echo "dbt_release=${latest_dbt}" >> $GITHUB_OUTPUT
    return 0
  fi
  echo "dbt_release=${current_dbt}" >> $GITHUB_OUTPUT
  return 1
}

cp generated-files/releases.json generated-files/updated-releases.json

ol_version
ol_version_changed=$?
dbt_version
dbt_version_changed=$?

if ((ol_version_changed == 0)) || ((dbt_version_changed == 0)); then
  echo "releases_updated=true" >> $GITHUB_OUTPUT
fi