#!/bin/bash

# Installs OpenLineage jar onto a Cloud Dataproc cluster.

set -euxo pipefail

readonly VM_SPARK_JARS_DIR=/usr/lib/spark/jars
readonly SPARK_BQ_CONNECTOR_URL=$(/usr/share/google/get_metadata_value attributes/SPARK_BQ_CONNECTOR_URL || echo "")
readonly OPENLINEAGE_SPARK_URL=$(/usr/share/google/get_metadata_value attributes/OPENLINEAGE_SPARK_URL || echo "")
readonly SPARK_SPANNER_CONNECTOR_URL=$(/usr/share/google/get_metadata_value attributes/SPARK_SPANNER_CONNECTOR_URL || echo "")
readonly SPARK_BIGTABLE_CONNECTOR_URL=$(/usr/share/google/get_metadata_value attributes/SPARK_BIGTABLE_CONNECTOR_URL || echo "")


if [[ -n "${OPENLINEAGE_SPARK_URL}" ]]; then
    bq_url="${SPARK_BQ_CONNECTOR_URL}"
    ol_url="${OPENLINEAGE_SPARK_URL}"
    spanner_url="${SPARK_SPANNER_CONNECTOR_URL}"
else
    bq_url="gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.0.1-SNAPSHOT.jar"
    ol_url="gs://open-lineage-e2e/jars/openlineage-spark_2.12-1.29.0-SNAPSHOT.jar"
    spanner_url="gs://open-lineage-e2e/jars/spark-3.1-spanner-1.1.0.jar"
    bigtable_url="gs://open-lineage-e2e/jars/spark-bigtable_2.12-0.3.0.jar"
fi

postgresql_url="gs://open-lineage-e2e/jars/postgresql-42.5.6.jar"

gsutil cp -P "${bq_url}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${ol_url}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${spanner_url}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${postgresql_url}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${bigtable_url}" "${VM_SPARK_JARS_DIR}/"