#!/bin/bash

# Installs OpenLineage jar onto a Cloud Dataproc cluster.

set -euxo pipefail

readonly VM_SPARK_JARS_DIR=/usr/lib/spark/jars

readonly SPARK_BQ_CONNECTOR_URL=$(/usr/share/google/get_metadata_value attributes/SPARK_BQ_CONNECTOR_URL || echo "gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.0.1-SNAPSHOT.jar")
readonly OPENLINEAGE_SPARK_URL=$(/usr/share/google/get_metadata_value attributes/OPENLINEAGE_SPARK_URL || echo "gs://open-lineage-e2e/jars/openlineage-spark_2.12-1.29.0-SNAPSHOT.jar")
readonly SPARK_SPANNER_CONNECTOR_URL=$(/usr/share/google/get_metadata_value attributes/SPARK_SPANNER_CONNECTOR_URL || echo "gs://open-lineage-e2e/jars/spark-3.1-spanner-1.1.0.jar")
readonly SPARK_BIGTABLE_CONNECTOR_URL=$(/usr/share/google/get_metadata_value attributes/SPARK_BIGTABLE_CONNECTOR_URL || echo "")
readonly POSTGRES_URL=$(/usr/share/google/get_metadata_value attributes/POSTGRES_URL || echo "gs://open-lineage-e2e/jars/postgresql-42.5.6.jar")

gsutil cp -P "${SPARK_BQ_CONNECTOR_URL}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${OPENLINEAGE_SPARK_URL}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${SPARK_SPANNER_CONNECTOR_URL}" "${VM_SPARK_JARS_DIR}/"
gsutil cp -P "${POSTGRES_URL}" "${VM_SPARK_JARS_DIR}/"
[[ -n "${SPARK_BIGTABLE_CONNECTOR_URL}" ]] && gsutil cp -P "${SPARK_BIGTABLE_CONNECTOR_URL}" "${VM_SPARK_JARS_DIR}/"
