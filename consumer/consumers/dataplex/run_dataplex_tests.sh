usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --gcp-credentials-json-path PATH    Path to GCP credentials JSON (required)"
    echo "  --consumer-dir PATH                 Scenario path (default:)"
    echo "  --scenario-dir PATH                 Consumer path (default:) "
    echo "  --gcp-parent PATH                   GCP parent (required)"
    echo "  --dump-api-state                    Flag to dump API state (default: false)"
    echo "  -h, --help                          Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 --gcp-credentials-json-path /path/to/credentials.json --gcs-transport-jar-path /path/to/jar --dump-api-state"
    exit 0
}

GCP_CREDENTIALS_JSON_PATH=""
CONSUMER_DIR="./"
SCENARIO_DIR="../scenarios"
GCP_PARENT=""
DUMP_API_STATE=""

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    usage
fi

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --gcp-credentials-json-path) GCP_CREDENTIALS_JSON_PATH="$2"; shift ;;
        --consumer-dir) CONSUMER_DIR="$2"; shift ;;
        --scenario-dir) SCENARIO_DIR="$2"; shift ;;
        --gcp-parent) GCP_PARENT="$2"; shift ;;
        --dump-api-state) DUMP_API_STATE='--dump' ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

# Check required arguments
if [[ -z "$GCP_CREDENTIALS_JSON_PATH" || -z "$GCP_PARENT" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

[[ "$(python3 --version 2>&1)" =~ ^Python\ 3\.11\.* ]] || { echo "Python version 3.11.x required. Detected: $PYTHON_VERSION"; exit 1; }

python -m pip install --upgrade pip
pip install flake8 pytest
if [ -f consumer/consumers/dataplex/validator/requirements.txt ]; then pip install -r consumer/consumers/dataplex/validator/requirements.txt; fi


python consumer/consumers/dataplex/validator/validator.py \
  --credentials "$GCP_CREDENTIALS_JSON_PATH" \
  --consumer_dir "$CONSUMER_DIR" \
  --scenario_dir "$SCENARIO_DIR" \
  --parent "$GCP_PARENT" ${DUMP_API_STATE} \
  --target "dataplex_report.json"