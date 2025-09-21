#!/bin/bash

################################################################################
############ Multi-Spec OpenLineage Compatibility Test Runner ################
################################################################################

# Help message function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --openlineage-directory PATH        Path to openlineage repository directory (required)"
    echo "  --spec-versions VERSIONS            Comma-separated list of spec versions (default: 2-0-2,2-0-1,1-1-1)"
    echo "  --producer-output-events-dir PATH   Path to producer output events directory (default: output)"
    echo "  -h, --help                          Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 --openlineage-directory /path/to/openlineage --spec-versions 2-0-2,2-0-1"
    exit 0
}

# Required variables
OPENLINEAGE_DIRECTORY=""

# Variables with default values
SPEC_VERSIONS="2-0-2,2-0-1,1-1-1"
PRODUCER_OUTPUT_EVENTS_DIR="output"

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --openlineage-directory) OPENLINEAGE_DIRECTORY="$2"; shift ;;
        --spec-versions) SPEC_VERSIONS="$2"; shift ;;
        --producer-output-events-dir) PRODUCER_OUTPUT_EVENTS_DIR="$2"; shift ;;
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

# Convert comma-separated versions to array
IFS=',' read -ra SPEC_VERSION_ARRAY <<< "$SPEC_VERSIONS"

echo "=============================================================================="
echo "              MULTI-SPEC OPENLINEAGE COMPATIBILITY TEST                      "
echo "=============================================================================="
echo "OpenLineage Directory: $OPENLINEAGE_DIRECTORY"
echo "Spec Versions to Test: ${SPEC_VERSIONS}"
echo "Output Directory: $PRODUCER_OUTPUT_EVENTS_DIR"
echo "=============================================================================="

# Results tracking
TOTAL_SPECS=${#SPEC_VERSION_ARRAY[@]}
PASSED_SPECS=0
FAILED_SPECS=0

# Run tests for each spec version
for spec_version in "${SPEC_VERSION_ARRAY[@]}"; do
    echo ""
    echo "🧪 TESTING AGAINST SPEC VERSION: $spec_version"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Run the test for this spec version
    if ./run_dbt_tests.sh \
        --openlineage-directory "$OPENLINEAGE_DIRECTORY" \
        --openlineage-release "$spec_version" \
        --producer-output-events-dir "$PRODUCER_OUTPUT_EVENTS_DIR"; then
        echo "✅ PASSED: Spec version $spec_version"
        PASSED_SPECS=$((PASSED_SPECS + 1))
    else
        echo "❌ FAILED: Spec version $spec_version"
        FAILED_SPECS=$((FAILED_SPECS + 1))
    fi
done

echo ""
echo "=============================================================================="
echo "                       MULTI-SPEC TEST SUMMARY                               "
echo "=============================================================================="
echo "Total spec versions tested: $TOTAL_SPECS"
echo "Passed spec versions: $PASSED_SPECS"
echo "Failed spec versions: $FAILED_SPECS"
echo ""
echo "📁 Results by spec version:"
for spec_version in "${SPEC_VERSION_ARRAY[@]}"; do
    events_file="$PRODUCER_OUTPUT_EVENTS_DIR/spec_$spec_version/openlineage_events_${spec_version}.jsonl"
    report_file="output/dbt_producer_report_${spec_version}.json"
    
    if [[ -f "$events_file" ]]; then
        event_count=$(wc -l < "$events_file" 2>/dev/null || echo "0")
        echo "  📋 Spec $spec_version: $event_count events → $events_file"
    else
        echo "  ❌ Spec $spec_version: No events generated"
    fi
    
    if [[ -f "$report_file" ]]; then
        echo "  📊 Spec $spec_version: Report → $report_file"
    else
        echo "  ❌ Spec $spec_version: No report generated"
    fi
done
echo "=============================================================================="

# Exit with appropriate code
if [[ $FAILED_SPECS -eq 0 ]]; then
    echo "🎉 ALL SPEC VERSIONS PASSED!"
    exit 0
else
    echo "⚠️  Some spec versions failed. Check logs above."
    exit 1
fi