#!/bin/bash

# Dataproc initialization action shared by every Dataproc producer. It copies the jars the cluster metadata lists and
# nothing else: which jars a component version needs is decided by the producer (runner/cluster.json), so there are
# no defaults here. A jar that can't be copied fails the init action, and with it the cluster creation.
#
# Metadata:
#   JARS             gs:// URLs separated by semicolons, copied to JARS_TARGET_DIR on every node
#   JARS_TARGET_DIR  e.g. /usr/lib/spark/jars; default: the Dataproc lib dir if present, otherwise /usr/lib/hadoop/lib
#   MASTER_JARS      <local dir>=<gs:// URL> entries separated by semicolons, copied on the master only
#                    (e.g. one OpenLineage jar per version, chosen per job)

set -euxo pipefail

readonly GET_METADATA="${GET_METADATA:-/usr/share/google/get_metadata_value}"
readonly DATAPROC_LIB_DIR="${DATAPROC_LIB_DIR:-/usr/local/share/google/dataproc/lib}"
readonly HADOOP_LIB_DIR="${HADOOP_LIB_DIR:-/usr/lib/hadoop/lib}"

metadata() {
  "$GET_METADATA" "attributes/$1" 2> /dev/null || true
}

jars=$(metadata JARS)
master_jars=$(metadata MASTER_JARS)
target_dir=$(metadata JARS_TARGET_DIR)
role=$(metadata dataproc-role)

if [[ -z "$target_dir" ]]; then
  if [[ -d "$DATAPROC_LIB_DIR" ]]; then
    target_dir="$DATAPROC_LIB_DIR"
  else
    target_dir="$HADOOP_LIB_DIR"
  fi
fi

if [[ -n "$jars" ]]; then
  IFS=';' read -ra jar_urls <<< "$jars"
  for url in "${jar_urls[@]}"; do
    [[ -n "$url" ]] && gsutil cp -P "$url" "$target_dir/"
  done
fi

if [[ "$role" == "Master" && -n "$master_jars" ]]; then
  IFS=';' read -ra entries <<< "$master_jars"
  for entry in "${entries[@]}"; do
    [[ -z "$entry" ]] && continue
    dir="${entry%%=*}"
    mkdir -p "$dir"
    gsutil cp "${entry#*=}" "$dir/"
  done
fi
