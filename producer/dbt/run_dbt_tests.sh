#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DBT_DIR="$SCRIPT_DIR"
REPO_ROOT="$(cd "$DBT_DIR/../.." && pwd)"
SCENARIOS_DIR="$DBT_DIR/scenarios"
RUNNER_REQUIREMENTS="$DBT_DIR/runner/requirements.txt"
SPECS_BASE_DIR="$DBT_DIR/specs"
SCRIPTS_DIR="$REPO_ROOT/scripts"

resolve_path() {
    local input_path="$1"
    local base_dir="$2"
    if [[ "$input_path" == ~* ]]; then
        input_path="${input_path/#\~/$HOME}"
    fi
    if [[ "$input_path" = /* ]]; then
        echo "$input_path"
    else
        echo "$base_dir/$input_path"
    fi
}

################################################################################
############ dbt Producer Compatibility Test Execution Script ################
################################################################################

# Help message function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --openlineage-directory PATH        Path to openlineage repository directory (required)"
    echo "  --producer-output-events-dir PATH   Path to producer output events directory (default: <script_dir>/output)"
    echo "  --openlineage-release VERSION       OpenLineage release version (default: 1.40.1)"
    echo "  --report-path PATH                  Path to report file (default: <repo_root>/dbt_producer_report.json)"
    echo "  -h, --help                          Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 --openlineage-directory /path/to/OpenLineage --producer-output-events-dir /tmp/dbt-output --openlineage-release 1.45.0"
    exit 0
}

# Required variables (no defaults)
OPENLINEAGE_DIRECTORY=""

# Variables with default values
PRODUCER_OUTPUT_EVENTS_DIR="$DBT_DIR/output"
OPENLINEAGE_RELEASE=1.40.1
REPORT_PATH="$REPO_ROOT/dbt_producer_report.json"

# If -h or --help is passed, print usage and exit
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    usage
fi

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --openlineage-directory) OPENLINEAGE_DIRECTORY="$2"; shift ;;
        --producer-output-events-dir) PRODUCER_OUTPUT_EVENTS_DIR="$2"; shift ;;
        --openlineage-release) OPENLINEAGE_RELEASE="$2"; shift ;;
        --report-path) REPORT_PATH="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

OPENLINEAGE_DIRECTORY="$(resolve_path "$OPENLINEAGE_DIRECTORY" "$PWD")"
PRODUCER_OUTPUT_EVENTS_DIR="$(resolve_path "$PRODUCER_OUTPUT_EVENTS_DIR" "$PWD")"
REPORT_PATH="$(resolve_path "$REPORT_PATH" "$PWD")"

# Check required arguments
if [[ -z "$OPENLINEAGE_DIRECTORY" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

# fail if scenarios are not defined in scenario directory
[[ -d "$SCENARIOS_DIR" ]] || { echo >&2 "Error: scenarios directory not found at $SCENARIOS_DIR"; exit 1; }
[[ $(find "$SCENARIOS_DIR" | wc -l) -gt 0 ]] || { echo >&2 "NO SCENARIOS DEFINED IN $SCENARIOS_DIR"; exit 1; }

mkdir -p "$PRODUCER_OUTPUT_EVENTS_DIR"

echo "=============================================================================="
echo "                    dbt PRODUCER COMPATIBILITY TEST                           "
echo "=============================================================================="
echo "OpenLineage Directory: $OPENLINEAGE_DIRECTORY"
echo "Producer Output Events Dir: $PRODUCER_OUTPUT_EVENTS_DIR"
echo "OpenLineage Release: $OPENLINEAGE_RELEASE"
echo "Report Path: $REPORT_PATH"
echo "=============================================================================="

################################################################################
#
# SETUP ENVIRONMENT
#
################################################################################

# Check if scenario directory exists
if [[ ! -d "$SCENARIOS_DIR" ]]; then
    echo "Error: scenarios directory not found at $SCENARIOS_DIR"
    exit 1
fi

#install python dependencies
python -m pip install --upgrade pip

if [ -f "$RUNNER_REQUIREMENTS" ]; then
  pip install -r "$RUNNER_REQUIREMENTS"
fi

################################################################################
#
# RUN dbt PRODUCER TESTS
#
################################################################################

echo "Running dbt producer tests..."

# Run tests for each scenario
echo "Discovering test scenarios..."
for scenario_dir in "$SCENARIOS_DIR"/*/; do
    if [[ -d "$scenario_dir" && -f "${scenario_dir}config.json" ]]; then
        SCENARIO_NAME=$(basename "$scenario_dir")
        echo "Found scenario: $SCENARIO_NAME"

        mkdir -p "$PRODUCER_OUTPUT_EVENTS_DIR/$SCENARIO_NAME"
        "$scenario_dir"test/run.sh "$PRODUCER_OUTPUT_EVENTS_DIR/$SCENARIO_NAME"

        echo "Scenario $SCENARIO_NAME completed"
    fi
done

echo "EVENT VALIDATION FOR SPEC VERSION $OPENLINEAGE_RELEASE"

# Generate JSON report
REPORT_DIR=$(dirname "$REPORT_PATH")
mkdir -p "$REPORT_DIR"

DEST_DIR="$SPECS_BASE_DIR/$OPENLINEAGE_RELEASE"

mkdir -p "$DEST_DIR"

if [ -d "$OPENLINEAGE_DIRECTORY/spec" ]; then
  while IFS= read -r spec_file; do
    cp "$spec_file" "$DEST_DIR/"
  done < <(find "$OPENLINEAGE_DIRECTORY/spec" -type f \( -name '*Facet.json' -o -name 'OpenLineage.json' \))
fi
if [ -d "$OPENLINEAGE_DIRECTORY/integration/common/src/openlineage" ]; then
  while IFS= read -r spec_file; do
    cp "$spec_file" "$DEST_DIR/"
  done < <(find "$OPENLINEAGE_DIRECTORY/integration/common/src/openlineage" -type f -iname '*facet.json')
fi

if [ -z "$(ls -A "$DEST_DIR")" ]; then
    echo "Cannot collect OpenLineage specs"
    exit 1
fi

pip install -r "$SCRIPTS_DIR/requirements.txt"

python "$SCRIPTS_DIR/validate_ol_events.py" \
--event_base_dir="$PRODUCER_OUTPUT_EVENTS_DIR" \
--spec_base_dir="$SPECS_BASE_DIR" \
--target="$REPORT_PATH" \
--component="dbt" \
--component_version="1.8.0" \
--producer_dir="$REPO_ROOT/producer" \
--openlineage_version="$OPENLINEAGE_RELEASE"

echo "EVENT VALIDATION FINISHED"
echo "REPORT CREATED IN $REPORT_PATH"