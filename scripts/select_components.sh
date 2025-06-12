# assuming the version will not exceed 1000 this is the quickest way to get comparable values
version_sum() {
  IFS='.' read -r var1 var2 var3 <<< "$1"
  echo $(( var1 * 1000000 + var2 * 1000 + var3))
}

current_ol=$(cat generated-files/releases.json | jq -c '.[] | select(.name | contains("openlineage")) | .latest_version ' -r)
latest_ol=$(curl https://api.github.com/repos/OpenLineage/OpenLineage/releases/latest -s | jq .tag_name -r)

if (( $(version_sum $latest_ol) > $(version_sum $current_ol) )); then
    echo "ol_release=${latest_ol}" >> $GITHUB_OUTPUT
    echo "releases_updated=true" >> $GITHUB_OUTPUT
    jq --arg latest_ol "$latest_ol" 'map(if .name == "openlineage" then .latest_version = $latest_ol else . end)' \
    generated-files/releases.json > generated-files/updated-releases.json
else
    echo "ol_release=${current_ol}" >> $GITHUB_OUTPUT
fi