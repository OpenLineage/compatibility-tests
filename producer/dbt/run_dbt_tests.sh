#!/bin/bash

################################################################################
############ dbt Producer Compatibility Test Execution Script ################
################################################################################

# Help message function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --openlineage-directory PATH        Path to openlineage repository directory (required)"
    echo "  --producer-output-events-dir PATH   Path to producer output events directory (default: output)"
    echo "  --openlineage-release VERSION       OpenLineage release version (default: 2-0-2)"
    echo "  --report-path PATH                  Path to report directory (default: ../dbt_producer_report.json)"
    echo "  -h, --help                          Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 --openlineage-directory /path/to/specs --producer-output-events-dir output --openlineage-release 2-0-2"
    exit 0
}

# Required variables (no defaults)
OPENLINEAGE_DIRECTORY=""

# Variables with default values
PRODUCER_OUTPUT_EVENTS_DIR=output
OPENLINEAGE_RELEASE=1.41.0
REPORT_PATH="./dbt_producer_report.json"

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

# Check required arguments
if [[ -z "$OPENLINEAGE_DIRECTORY" ]]; then
    echo "Error: Missing required arguments."
    usage
fi

# fail if scenarios are not defined in scenario directory
[[ $(find scenarios | wc -l) -gt 0 ]] || { echo >&2 "NO SCENARIOS DEFINED IN scenarios"; exit 1; }

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
if [[ ! -d "scenarios" ]]; then
    echo "Error: scenarios directory not found"
    exit 1
fi

#install python dependencies
#python -m pip install --upgrade pip
#
#if [ -f ./runner/requirements.txt ]; then
#  pip install -r ./runner/requirements.txt
#fi

################################################################################
#
# RUN dbt PRODUCER TESTS
#
################################################################################

echo "Running dbt producer tests..."
POSIX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cygpath -m "$POSIX_DIR")"

# Run tests for each scenario
echo "Discovering test scenarios..."
for scenario_dir in scenarios/*/; do
    if [[ -d "$scenario_dir" && -f "${scenario_dir}config.json" ]]; then
        SCENARIO_NAME=$(basename "$scenario_dir")
        echo "Found scenario: $SCENARIO_NAME"

        mkdir -p "$PRODUCER_OUTPUT_EVENTS_DIR/$SCENARIO_NAME"
        "$scenario_dir"test/run.sh "$BASE_DIR/$PRODUCER_OUTPUT_EVENTS_DIR/$SCENARIO_NAME"

        echo "Scenario $SCENARIO_NAME completed"
    fi
done

echo "EVENT VALIDATION FOR SPEC VERSION $OPENLINEAGE_RELEASE"

# Generate JSON report
REPORT_DIR=$(dirname "$REPORT_PATH")
mkdir -p "$REPORT_DIR"

SPECS_BASE_DIR="./specs"
DEST_DIR="$SPECS_BASE_DIR/$OPENLINEAGE_RELEASE"

mkdir -p "$DEST_DIR"

if [ -d "$OPENLINEAGE_DIRECTORY"/spec ]; then
  find "$OPENLINEAGE_DIRECTORY"/spec -type f \( -name '*Facet.json' -o -name 'OpenLineage.json' \) -exec cp -t "$DEST_DIR" {} +
fi
if [ -d "$OPENLINEAGE_DIRECTORY"/integration/common/openlineage ]; then
  find "$OPENLINEAGE_DIRECTORY"/integration/common/openlineage -type f -iname '*facet.json' -exec cp -t "$DEST_DIR" {} +
fi

if [ -z "$(ls -A "$DEST_DIR")" ]; then
    echo "Cannot collect OpenLineage specs"
    exit 1
fi

#pip install -r ../../scripts/requirements.txt

python ../../scripts/validate_ol_events.py \
--event_base_dir="$PRODUCER_OUTPUT_EVENTS_DIR" \
--spec_base_dir="$SPECS_BASE_DIR" \
--target="$REPORT_PATH" \
--component="scenarios" \
--producer_dir=. \
--openlineage_version="$OPENLINEAGE_RELEASE"

echo "EVENT VALIDATION FINISHED"
echo "REPORT CREATED IN $REPORT_PATH"