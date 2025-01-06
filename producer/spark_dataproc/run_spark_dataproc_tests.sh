# FIXME THIS IS STILL IN PROGRESS, NOT TESTED


# Help message function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --gcp-credentials-json-path PATH    Path to GCP credentials JSON (required)"
    echo "  --gcs-transport-jar-path PATH       Path to GCS transport JAR (required)"
    echo "  --openlineage-directory PATH        Path to openlineage repository directory (required)"
    echo "  --gcp-project PROJECT_ID            GCP project ID (required)"
    echo "  --gcp-region REGION                 GCP region (required)"
    echo "  --gcs-bucket BUCKET_NAME            GCS bucket name (required)"
    echo "  --dataproc-cluster-name NAME        Dataproc cluster name (required)"
    echo "  --producer-output-events-dir PATH   Path to producer output events directory (default: /path/to/default/events/dir)"
    echo "  --openlineage-release VERSION       OpenLineage release version (default: default-openlineage-release)"
    echo "  --report-path PATH                  Path to report directory (default: /path/to/default/report)"
    echo "  -h, --help                          Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 --gcp-credentials-json-path /path/to/credentials.json --gcs-transport-jar-path /path/to/jar --openlineage-directory /path/to/specs --gcp-project my-project --gcp-region us-central1 --gcs-bucket my-bucket --dataproc-cluster-name my-cluster"
    exit 0
}

# Required variables (no defaults)
GCP_CREDENTIALS_JSON_PATH=""
GCS_TRANSPORT_JAR_PATH=""
OPENLINEAGE_DIRECTORY=""
GCP_PROJECT=""
GCP_REGION=""
GCS_BUCKET=""
DATAPROC_CLUSTER_NAME=""

# Variables with default values
PRODUCER_OUTPUT_EVENTS_DIR=output
OPENLINEAGE_RELEASE=1.23.0
REPORT_PATH="../spark_dataproc_report.json"

# If -h or --help is passed, print usage and exit
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    usage
fi

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --gcp-credentials-json-path) GCP_CREDENTIALS_JSON_PATH="$2"; shift ;;
        --gcs-transport-jar-path) GCS_TRANSPORT_JAR_PATH="$2"; shift ;;
        --openlineage-directory) OPENLINEAGE_DIRECTORY="$2"; shift ;;
        --gcp-project) GCP_PROJECT="$2"; shift ;;
        --gcp-region) GCP_REGION="$2"; shift ;;
        --gcs-bucket) GCS_BUCKET="$2"; shift ;;
        --dataproc-cluster-name) DATAPROC_CLUSTER_NAME="$2"; shift ;;
        --producer-output-events-dir) PRODUCER_OUTPUT_EVENTS_DIR="$2"; shift ;;
        --openlineage-release) OPENLINEAGE_RELEASE="$2"; shift ;;
        --report-path) REPORT_PATH="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

# Check required arguments
if [[ -z "$GCP_CREDENTIALS_JSON_PATH" || -z "$GCS_TRANSPORT_JAR_PATH" || -z "$OPENLINEAGE_DIRECTORY" || -z "$GCP_PROJECT" || -z "$GCP_REGION" || -z "$GCS_BUCKET" || -z "$DATAPROC_CLUSTER_NAME" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

#./run_spark_dataproc_tests.sh --gcp-credentials-json-path /path/to/credentials.json \
#--gcs-transport-jar-path  \
#--openlineage-directory ~/projects/OpenLineage \
#--gcp-project my-project \
#--gcp-region us-central1 \
#--gcs-bucket my-bucket \
#--dataproc-cluster-name manual-test-cluster-1
#
##=============================================== START CLUSTER =========================================================
#
#python producer/spark_dataproc/runner/dataproc_workflow.py create-cluster \
#  --project-id gcp-open-lineage-testing \
#  --region us-west1 \
#  --cluster-name manual-test-cluster-6 \
#  --credentials-file /Users/tomasznazarewicz/projects/open-lineage-tests/ignored/gcp-open-lineage-testing-6d2aa0caca8e.json \
#  --metadata "SPARK_BQ_CONNECTOR_URL=gs://open-lineage-e2e/jars/spark-3.5-bigquery-0.0.1-SNAPSHOT.jar,OPENLINEAGE_SPARK_URL=gs://open-lineage-e2e/jars/openlineage-spark_2.12-1.25.0-SNAPSHOT.jar" \
#  --initialization-actions="gs://open-lineage-e2e/scripts/get_openlineage_jar.sh"
#
##============================================= TERMINATE CLUSTER =======================================================
#
#python producer/spark_dataproc/runner/dataproc_workflow.py terminate-cluster \
#  --project-id gcp-open-lineage-testing \
#  --region us-west1 \
#  --cluster-name manual-test-cluster-6 \
#  --credentials-file  /Users/tomasznazarewicz/projects/open-lineage-tests/ignored/gcp-open-lineage-testing-6d2aa0caca8e.json
#
##================================================== RUN JOB ============================================================
#
#scenario="bigquery_input"
#scenario_path="producer/spark_dataproc/scenarios/$scenario"
#run_script=$(find "$scenario_path/test" -maxdepth 1 -type f -name "*.py" | head -n 1)
#
#echo "Running spark job for scenario: $scenario"
#
#python producer/spark_dataproc/runner/dataproc_workflow.py run-job \
#--project-id gcp-open-lineage-testing \
#--region us-west1 \
#--cluster-name manual-test-cluster-6 \
#--gcs-bucket open-lineage-e2e \
#--python-job "$run_script" \
#--jars "gs://open-lineage-e2e/jars/transports-gcs-1.25.0-SNAPSHOT.jar" \
#--spark-properties "spark.extraListeners=io.openlineage.spark.agent.OpenLineageSparkListener,spark.sql.warehouse.dir=/tmp/warehouse,spark.openlineage.transport.type=gcs" \
#--output-directory "/tmp/manual-test-output/$scenario" \
#--credentials-file "/Users/tomasznazarewicz/projects/open-lineage-tests/ignored/gcp-open-lineage-testing-6d2aa0caca8e.json" \
#--dataproc-image-version 2.2-ubuntu22
#
##=======================================================================================================================
#
#gcloud dataproc jobs describe acee19d9-6f97-4b6f-b947-3a4366e7894e --region us-west1
#
#gsutil cp gs://dataproc-staging-us-west1-484892851355-unzodmbv/google-cloud-dataproc-metainfo/972858e5-565c-404e-af16-38eb4a3ec465/jobs/acee19d9-6f97-4b6f-b947-3a4366e7894e/driveroutput .
#gsutil ls gs://dataproc-staging-us-west1-484892851355-unzodmbv/google-cloud-dataproc-metainfo/972858e5-565c-404e-af16-38eb4a3ec465/jobs/acee19d9-6f97-4b6f-b947-3a4366e7894e/driveroutput


OL_SPEC_DIRECTORIES=$OPENLINEAGE_DIRECTORY/spec/,$OPENLINEAGE_DIRECTORY/spec/facets/,$OPENLINEAGE_DIRECTORY/spec/registry/gcp/dataproc/facets,$OPENLINEAGE_DIRECTORY/spec/registry/gcp/lineage/facets

# fail if scenarios are not defined in scenario directory
[[ $(ls scenarios | wc -l) -gt 0 ]] || { echo >&2 "NO SCENARIOS DEFINED IN scenarios"; exit 1; }
# fail if gsutil is not installed
command -v gsutil >/dev/null 2>&1   || { echo >&2 "gsutil is required see https://cloud.google.com/storage/docs/gsutil_install"; exit 1; }

mkdir -p "$PRODUCER_OUTPUT_EVENTS_DIR"

#install python dependencies
python -m pip install --upgrade pip
pip install flake8 pytest
if [ -f requirements.txt ];
then
  pip install -r requirements.txt
fi



# start the cluster
echo "STARTING DATAPROC CLUSTER"
python producer/spark_dataproc/runner/dataproc_workflow.py create-cluster \
  --project-id "$GCP_PROJECT" \
  --region "$GCP_REGION" \
  --cluster-name "$DATAPROC_CLUSTER_NAME" \
  --credentials-file "$GCP_CREDENTIALS_JSON_PATH" \
  --metadata "SPARK_BQ_CONNECTOR_URL=gs://$GCS_BUCKET/jars/spark-3.5-bigquery-0.41.0.jar,OPENLINEAGE_SPARK_URL=gs://$GCS_BUCKET/jars/openlineage-spark_2.12-$OPENLINEAGE_RELEASE.jar" \
  --initialization-actions="gs://$GCS_BUCKET/scripts/get_openlineage_jar.sh"

echo "DATAPROC CLUSTER STARTED"

for scenario_path in scenarios/*
do
  scenario="${scenario_path##*/}"
  echo "RUNNING SPARK JOB FOR $scenario SCENARIO"

  python producer/spark_dataproc/runner/dataproc_workflow.py run-job \
    --project-id gcp-open-lineage-testing \
    --region us-west1 \
    --cluster-name dataproc-producer-test \
    --gcs-bucket "$GCS_BUCKET" \
    --python-job producer/spark_dataproc/scenarios/$scenario/test/test.py \
    --jars "$GCS_TRANSPORT_JAR_PATH" \
    --spark-properties "spark.extraListeners=io.openlineage.spark.agent.OpenLineageSparkListener,spark.sql.warehouse.dir=/tmp/warehouse,spark.openlineage.transport.type=gcs" \
    --output-directory "$PRODUCER_EVENTS_DIR/$scenario" \
    --credentials-file "$GCP_CREDENTIALS_JSON_PATH" \
    --dataproc-image-version 2.2-ubuntu22 \
    --job-args "file:///tmp/outputs/$(date +%s%3N)"

done

python producer/spark_dataproc/runner/dataproc_workflow.py terminate-cluster \
  --project-id "$GCP_PROJECT" \
  --region "$GCP_REGION" \
  --cluster-name "$DATAPROC_CLUSTER_NAME" \
  --credentials-file "$GCP_CREDENTIALS_JSON_PATH"

echo "TERMINATING DATAPROC CLUSTER"

echo "EVENT VALIDATION"

pip install -r ./scripts/requirements.txt

python ../../scripts/validate_ol_events.py \
--event_base_dir="$PRODUCER_OUTPUT_EVENTS_DIR" \
--spec_dirs="$OL_SPEC_DIRECTORIES" \
--target="$REPORT_PATH" \
--component="spark_dataproc" \
--producer_dir=.

echo "EVENT VALIDATION FINISHED"
echo "REPORT CREATED IN $REPORT_PATH"