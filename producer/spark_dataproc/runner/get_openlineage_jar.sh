#!/bin/bash

# Installs OpenLineage jar onto a Cloud Dataproc cluster.

set -euxo pipefail

readonly VM_SPARK_JARS_DIR=/usr/lib/spark/jars
readonly SKIP_ICEBERG_AND_DELTA=$(/usr/share/google/get_metadata_value attributes/SKIP_ICEBERG_AND_DELTA || echo "")
# '<version>:<spark jar>:<gcs transport jar>' entries separated by semicolons, jars are in JARS_DIR
# (see stage_openlineage_jars.sh). When set, each version is copied to OPENLINEAGE_LOCAL_DIR/<version> on the
# master only and the jobs choose one with spark.driver.extraClassPath, otherwise the single
# OPENLINEAGE_SPARK_URL jar is installed.
readonly OPENLINEAGE_JARS=$(/usr/share/google/get_metadata_value attributes/OPENLINEAGE_JARS || echo "")
readonly OPENLINEAGE_LOCAL_DIR=/opt/openlineage
readonly JARS_DIR=gs://open-lineage-e2e/jars
readonly ROLE=$(/usr/share/google/get_metadata_value attributes/dataproc-role)

# Returns the metadata attribute value, or the given default when the attribute is not set.
metadata_or_default() {
  local value
  value=$(/usr/share/google/get_metadata_value "attributes/$1" || echo "")
  echo "${value:-$2}"
}

bq_url=$(metadata_or_default SPARK_BQ_CONNECTOR_URL "gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.42.4.jar")
ol_url=$(metadata_or_default OPENLINEAGE_SPARK_URL "gs://open-lineage-e2e/jars/openlineage-spark_2.12-1.29.0-SNAPSHOT.jar")
spanner_url=$(metadata_or_default SPARK_SPANNER_CONNECTOR_URL "gs://open-lineage-e2e/jars/spark-3.1-spanner-1.1.0.jar")
bigtable_url=$(metadata_or_default SPARK_BIGTABLE_CONNECTOR_URL "gs://open-lineage-e2e/jars/spark-bigtable_2.12-0.3.0.jar")

postgresql_url="gs://open-lineage-e2e/jars/postgresql-42.5.6.jar"
delta_spark_url="gs://open-lineage-e2e/jars/delta-spark_2.12-3.3.1.jar"
delta_storage_url="gs://open-lineage-e2e/jars/delta-storage-3.3.1.jar"
iceberg_spark_runtime_url="gs://open-lineage-e2e/jars/iceberg-spark-runtime-3.5_2.12-1.10.0.jar"
iceberg_gcp_bundle_url="gs://open-lineage-e2e/jars/iceberg-gcp-bundle-1.10.0.jar"
iceberg_bigquery_url="gs://open-lineage-e2e/jars/iceberg-bigquery-1.10.0.jar"


gsutil cp -P "${bq_url}" "${VM_SPARK_JARS_DIR}/"
if [[ -z "${OPENLINEAGE_JARS}" ]]; then
  gsutil cp -P "${ol_url}" "${VM_SPARK_JARS_DIR}/"
elif [[ "${ROLE}" == "Master" ]]; then
  IFS=';' read -ra ol_entries <<< "${OPENLINEAGE_JARS}"
  for entry in "${ol_entries[@]}"; do
    IFS=':' read -r version spark_jar gcs_jar <<< "${entry}"
    mkdir -p "${OPENLINEAGE_LOCAL_DIR}/${version}"
    gsutil cp "${JARS_DIR}/${spark_jar}" "${JARS_DIR}/${gcs_jar}" "${OPENLINEAGE_LOCAL_DIR}/${version}/"
  done
fi
gsutil cp -P "${spanner_url}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${bigtable_url}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${postgresql_url}" "${VM_SPARK_JARS_DIR}/"
if [[ "${SKIP_ICEBERG_AND_DELTA}" == "" ]]; then
  gsutil cp -P "${delta_spark_url}" "${VM_SPARK_JARS_DIR}/"
  gsutil cp -P "${delta_storage_url}" "${VM_SPARK_JARS_DIR}/"
  gsutil cp -P "${iceberg_spark_runtime_url}" "${VM_SPARK_JARS_DIR}/"
  gsutil cp -P "${iceberg_gcp_bundle_url}" "${VM_SPARK_JARS_DIR}/"
  gsutil cp -P "${iceberg_bigquery_url}" "${VM_SPARK_JARS_DIR}/"
fi