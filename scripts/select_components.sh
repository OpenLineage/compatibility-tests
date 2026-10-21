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
        'if any(.name == $name) then map(if .name == $name then .latest_version = $version else . end)
         else . + [{name: $name, latest_version: $version}] end' \
        generated-files/updated-releases.json > /tmp/releases.json \
  && mv /tmp/releases.json generated-files/updated-releases.json
}

ol_version() {
  current_ol=$(jq -r '.[] | select(.name | contains("openlineage")) | .latest_version ' generated-files/releases.json)
  latest_ol=$(curl https://api.github.com/repos/OpenLineage/OpenLineage/releases/latest -s | jq .tag_name -r)

  if (( $(version_sum $latest_ol) > $(version_sum $current_ol) )); then
    update_version "openlineage" "$latest_ol"
    echo "ol_release=${latest_ol}" >> $GITHUB_OUTPUT
    echo "ol_changed=true" >> $GITHUB_OUTPUT
    return 0
  fi
  echo "ol_release=${current_ol}" >> $GITHUB_OUTPUT
  return 1
}

dbt_version() {
  current_dbt=$(jq -r '.[] | select(.name | contains("dbt")) | .latest_version ' generated-files/releases.json)
  # PyPI JSON API instead of the output of the experimental `pip index`, whose format changed
  latest_dbt=$(curl -s https://pypi.org/pypi/dbt-core/json | jq -r '.info.version // empty')

  if [[ -z "$latest_dbt" ]]; then
    echo "::error::Could not get the latest dbt-core version from PyPI, keeping ${current_dbt}"
    echo "dbt_release=${current_dbt}" >> $GITHUB_OUTPUT
    return 1
  fi

  if (( $(version_sum $latest_dbt) > $(version_sum $current_dbt) )); then
    update_version "dbt" "$latest_dbt"
    echo "dbt_release=${latest_dbt}" >> $GITHUB_OUTPUT
    echo "dbt_changed=true" >> $GITHUB_OUTPUT
    return 0
  fi
  echo "dbt_release=${current_dbt}" >> $GITHUB_OUTPUT
  return 1
}

# Dataproc has no release numbers we could compare, but every release publishes a new image in each image family,
# so a family whose newest image differs from the one in releases.json got a new release
dataproc_version() {
  local changed=()
  for family in $(jq -r '.[]' producer/spark_dataproc/dataproc_images.json producer/hive_dataproc/dataproc_images.json | sort -u); do
    current_image=$(jq -r --arg name "$family" '.[] | select(.name == $name) | .latest_version' generated-files/releases.json)
    latest_image=$(gcloud compute images describe-from-family "$family" --project cloud-dataproc --format="value(name)" 2> /dev/null)

    if [[ -z "$latest_image" ]]; then
      echo "::error::Could not get the newest image of Dataproc image family ${family}"
    elif [[ "$latest_image" != "$current_image" ]]; then
      update_version "$family" "$latest_image"
      changed+=("$family")
    fi
  done

  echo "dataproc_changed_families=$(printf '%s\n' "${changed[@]}" | jq -R . | jq -sc 'map(select(. != ""))')" >> $GITHUB_OUTPUT
  (( ${#changed[@]} > 0 ))
}

cp generated-files/releases.json generated-files/updated-releases.json

ol_version
ol_version_changed=$?
dbt_version
dbt_version_changed=$?

dataproc_version
dataproc_version_changed=$?

if ((ol_version_changed == 0)) || ((dbt_version_changed == 0)) || ((dataproc_version_changed == 0)); then
  echo "releases_updated=true" >> $GITHUB_OUTPUT
fi