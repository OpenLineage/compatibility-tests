#!/bin/bash

# Prints the newest image of every Dataproc image family we test, as a JSON list of [family, image] pairs.
# Needs gcloud credentials. It runs in its own job because the GCP key is a multi-line secret: GitHub masks each of its
# lines, including the bare "{" and "}", and then drops every job output containing them, i.e. every JSON object.
# The output therefore must not contain braces.

set -uo pipefail

pairs='[]'
for family in $(jq -r '.[]' producer/spark_dataproc/dataproc_images.json producer/hive_dataproc/dataproc_images.json | sort -u); do
  image=$(gcloud compute images describe-from-family "$family" --project cloud-dataproc --format="value(name)" 2> /dev/null)

  if [[ -z "$image" ]]; then
    echo "::error::Could not get the newest image of Dataproc image family ${family}" >&2
    continue
  fi
  pairs=$(jq -c --arg family "$family" --arg image "$image" '. + [[$family, $image]]' <<< "$pairs")
done

echo "dataproc_images=$pairs"
