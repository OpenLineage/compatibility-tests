#!/bin/bash

# Installs OpenLineage jar onto a Cloud Dataproc cluster.

set -euxo pipefail

readonly VM_HADOOP_LIB_DIR=/usr/lib/hadoop/lib
readonly VM_DATAPROC_VM_HADOOP_LIB_DIR_DIR=/usr/local/share/google/dataproc/lib
readonly OPENLINEAGE_HIVE_URL=$(/usr/share/google/get_metadata_value attributes/OPENLINEAGE_HIVE_URL || echo "")
readonly GCS_TRANSPORT_JAR_URL=$(/usr/share/google/get_metadata_value attributes/GCS_TRANSPORT_JAR_URL || echo "")

if [[ -d ${VM_DATAPROC_VM_HADOOP_LIB_DIR_DIR} ]]; then
  vm_lib_dir=${VM_DATAPROC_VM_HADOOP_LIB_DIR_DIR}
else
  vm_lib_dir=${VM_HADOOP_LIB_DIR}
fi

copy_jar_or_default() {
    local path="$1"
    local default_path="$2"
    if [[ -n "${path}" ]]; then
        gsutil cp -P "${path}" "${vm_lib_dir}/"
    else
        gsutil cp -P "${default_path}" "${vm_lib_dir}/"
    fi
}

copy_jar_or_default "${OPENLINEAGE_HIVE_URL}" "gs://open-lineage-e2e/jars/openlineage-hive-1.34.0.jar "
copy_jar_or_default "${GCS_TRANSPORT_JAR_URL}" "gs://open-lineage-e2e/jars/transports-gcs-1.34.0.jar"

