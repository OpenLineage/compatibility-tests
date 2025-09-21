#!/bin/bash

################################################################################
########## TRUE Multi-Spec OpenLineage Compatibility Test Runner #############
################################################################################

# Help message function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "This script performs TRUE multi-spec testing by using different"
    echo "OpenLineage client library versions for each specification version."
    echo ""
    echo "Options:"
    echo "  --openlineage-directory PATH        Path to openlineage repository directory (required)"
    echo "  --spec-versions VERSIONS            Comma-separated list of spec versions (default: 2-0-2,2-0-1,1-1-1)"
    echo "  --producer-output-events-dir PATH   Path to producer output events directory (default: output)"
    echo "  --temp-venv-dir PATH                Directory for temporary virtual environments (default: temp_venvs)"
    echo "  -h, --help                          Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 --openlineage-directory /path/to/openlineage --spec-versions 2-0-2,2-0-1"
    echo ""
    echo "Requirements:"
    echo "  - Python 3.8+ with venv module"
    echo "  - pip"
    echo "  - dbt-core"
    echo "  - Different openlineage-python versions available on PyPI"
    exit 0
}

# Required variables
OPENLINEAGE_DIRECTORY=""

# Variables with default values
SPEC_VERSIONS="2-0-2,2-0-1,1-1-1"
PRODUCER_OUTPUT_EVENTS_DIR="output"
TEMP_VENV_DIR="temp_venvs"

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --openlineage-directory) OPENLINEAGE_DIRECTORY="$2"; shift ;;
        --spec-versions) SPEC_VERSIONS="$2"; shift ;;
        --producer-output-events-dir) PRODUCER_OUTPUT_EVENTS_DIR="$2"; shift ;;
        --temp-venv-dir) TEMP_VENV_DIR="$2"; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

# Check required arguments
if [[ -z "$OPENLINEAGE_DIRECTORY" ]]; then
    echo "Error: Missing required --openlineage-directory argument."
    usage
fi

# Mapping of spec versions to compatible OpenLineage client versions
# This would need to be researched and maintained
declare -A SPEC_TO_CLIENT_VERSION
SPEC_TO_CLIENT_VERSION["2-0-2"]="1.37.0"  # Latest version supporting 2-0-2
SPEC_TO_CLIENT_VERSION["2-0-1"]="1.35.0"  # Version that primarily used 2-0-1
SPEC_TO_CLIENT_VERSION["1-1-1"]="1.30.0"  # Version that used 1-1-1

# Convert comma-separated versions to array
IFS=',' read -ra SPEC_VERSION_ARRAY <<< "$SPEC_VERSIONS"

echo "=============================================================================="
echo "              TRUE MULTI-SPEC OPENLINEAGE COMPATIBILITY TEST                 "
echo "=============================================================================="
echo "OpenLineage Directory: $OPENLINEAGE_DIRECTORY"
echo "Spec Versions to Test: ${SPEC_VERSIONS}"
echo "Output Directory: $PRODUCER_OUTPUT_EVENTS_DIR"
echo "Temp VEnv Directory: $TEMP_VENV_DIR"
echo ""
echo "📦 Client Version Mapping:"
for spec_version in "${SPEC_VERSION_ARRAY[@]}"; do
    client_version="${SPEC_TO_CLIENT_VERSION[$spec_version]}"
    if [[ -n "$client_version" ]]; then
        echo "  Spec $spec_version → OpenLineage Client $client_version"
    else
        echo "  ❌ Spec $spec_version → No client version mapping found!"
    fi
done
echo "=============================================================================="

# Create temp venv directory
mkdir -p "$TEMP_VENV_DIR"

# Results tracking
TOTAL_SPECS=${#SPEC_VERSION_ARRAY[@]}
PASSED_SPECS=0
FAILED_SPECS=0

# Function to create virtual environment for specific OpenLineage version
create_spec_venv() {
    local spec_version="$1"
    local client_version="$2"
    local venv_path="$TEMP_VENV_DIR/venv_spec_${spec_version}"
    
    echo "📦 Creating virtual environment for spec $spec_version (client $client_version)..."
    
    # Remove existing venv if it exists
    rm -rf "$venv_path"
    
    # Create new virtual environment
    python3 -m venv "$venv_path"
    
    # Activate and install specific OpenLineage version
    source "$venv_path/bin/activate"
    
    pip install --upgrade pip
    pip install "openlineage-python==$client_version"
    pip install "openlineage-dbt"  # This might need version pinning too
    pip install dbt-core dbt-duckdb
    
    # Install other requirements
    if [[ -f "../../scripts/requirements.txt" ]]; then
        pip install -r ../../scripts/requirements.txt
    fi
    
    deactivate
    
    echo "✅ Virtual environment created: $venv_path"
}

# Function to run test in specific virtual environment
run_test_in_venv() {
    local spec_version="$1"
    local venv_path="$TEMP_VENV_DIR/venv_spec_${spec_version}"
    
    echo "🧪 Running test in venv for spec $spec_version..."
    
    # Activate the specific virtual environment
    source "$venv_path/bin/activate"
    
    # Verify we have the right version
    python -c "import openlineage; print(f'OpenLineage version: {openlineage.__version__}')" || true
    
    # Run the actual test
    local test_result=0
    ./run_dbt_tests.sh \
        --openlineage-directory "$OPENLINEAGE_DIRECTORY" \
        --openlineage-release "$spec_version" \
        --producer-output-events-dir "$PRODUCER_OUTPUT_EVENTS_DIR" || test_result=$?
    
    deactivate
    
    return $test_result
}

# Run tests for each spec version
for spec_version in "${SPEC_VERSION_ARRAY[@]}"; do
    echo ""
    echo "🧪 TESTING AGAINST SPEC VERSION: $spec_version"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    client_version="${SPEC_TO_CLIENT_VERSION[$spec_version]}"
    
    if [[ -z "$client_version" ]]; then
        echo "❌ SKIPPED: No client version mapping for spec $spec_version"
        FAILED_SPECS=$((FAILED_SPECS + 1))
        continue
    fi
    
    # Create virtual environment with specific OpenLineage version
    if create_spec_venv "$spec_version" "$client_version"; then
        # Run the test in that environment
        if run_test_in_venv "$spec_version"; then
            echo "✅ PASSED: Spec version $spec_version (client $client_version)"
            PASSED_SPECS=$((PASSED_SPECS + 1))
        else
            echo "❌ FAILED: Spec version $spec_version (client $client_version)"
            FAILED_SPECS=$((FAILED_SPECS + 1))
        fi
    else
        echo "❌ FAILED: Could not create venv for spec $spec_version"
        FAILED_SPECS=$((FAILED_SPECS + 1))
    fi
done

echo ""
echo "=============================================================================="
echo "                       TRUE MULTI-SPEC TEST SUMMARY                          "
echo "=============================================================================="
echo "Total spec versions tested: $TOTAL_SPECS"
echo "Passed spec versions: $PASSED_SPECS"
echo "Failed spec versions: $FAILED_SPECS"
echo ""
echo "📁 Results by spec version:"
for spec_version in "${SPEC_VERSION_ARRAY[@]}"; do
    client_version="${SPEC_TO_CLIENT_VERSION[$spec_version]}"
    events_file="$PRODUCER_OUTPUT_EVENTS_DIR/spec_$spec_version/openlineage_events_${spec_version}.jsonl"
    report_file="output/dbt_producer_report_${spec_version}.json"
    
    echo "  🔧 Spec $spec_version (Client $client_version):"
    
    if [[ -f "$events_file" ]]; then
        event_count=$(wc -l < "$events_file" 2>/dev/null || echo "0")
        echo "    📋 Events: $event_count → $events_file"
    else
        echo "    ❌ Events: No events generated"
    fi
    
    if [[ -f "$report_file" ]]; then
        echo "    📊 Report: $report_file"
    else
        echo "    ❌ Report: No report generated"
    fi
done

echo ""
echo "🧹 Cleanup:"
echo "  Virtual environments: $TEMP_VENV_DIR"
echo "  To clean up: rm -rf $TEMP_VENV_DIR"
echo "=============================================================================="

# Exit with appropriate code
if [[ $FAILED_SPECS -eq 0 ]]; then
    echo "🎉 ALL SPEC VERSIONS PASSED!"
    exit 0
else
    echo "⚠️  Some spec versions failed. Check logs above."
    exit 1
fi