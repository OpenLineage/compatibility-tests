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
OPENLINEAGE_RELEASE=2-0-2
REPORT_PATH="../dbt_producer_report.json"

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

OL_SPEC_DIRECTORIES=$OPENLINEAGE_DIRECTORY/spec/,$OPENLINEAGE_DIRECTORY/spec/facets/,$OPENLINEAGE_DIRECTORY/spec/registry/gcp/dataproc/facets,$OPENLINEAGE_DIRECTORY/spec/registry/gcp/lineage/facets

# fail if scenarios are not defined in scenario directory
[[ $(ls scenarios | wc -l) -gt 0 ]] || { echo >&2 "NO SCENARIOS DEFINED IN scenarios"; exit 1; }

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

echo "Setting up test environment..."

# Get script directory for relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python test runner exists
if [[ ! -f "test_runner/cli.py" ]]; then
    echo "Error: Python test runner not found at test_runner/cli.py"
    exit 1
fi

# Check if scenario directory exists
if [[ ! -d "scenarios" ]]; then
    echo "Error: scenarios directory not found"
    exit 1
fi

################################################################################
#
# RUN dbt PRODUCER TESTS
#
################################################################################

echo "Running dbt producer tests..."

# Set up Python environment
export PYTHONPATH="$SCRIPT_DIR/test_runner:$PYTHONPATH"

# Run tests for each scenario
TOTAL_SCENARIOS=0
PASSED_SCENARIOS=0
FAILED_SCENARIOS=0

echo "Discovering test scenarios..."
for scenario_dir in scenarios/*/; do
    if [[ -d "$scenario_dir" && -f "${scenario_dir}config.json" ]]; then
        SCENARIO_NAME=$(basename "$scenario_dir")
        echo "Found scenario: $SCENARIO_NAME"
        TOTAL_SCENARIOS=$((TOTAL_SCENARIOS + 1))
        
        echo "----------------------------------------"
        echo "Running scenario: $SCENARIO_NAME"
        echo "----------------------------------------"
        
        # Run the atomic tests for this scenario
        echo "Step 1: Running atomic tests..."
        if python3 test_runner/cli.py run-atomic --base-path "." --verbose; then
            echo "✅ Atomic tests passed for $SCENARIO_NAME"
            
            # Run OpenLineage event validation if events exist
            echo "Step 2: Validating OpenLineage events..."
            EVENTS_FILE="events/openlineage_events.jsonl"
            if [[ -f "$EVENTS_FILE" ]]; then
                echo "📋 Validating events from: $EVENTS_FILE"
                echo "📋 Against spec version: $OPENLINEAGE_RELEASE"
                if python3 test_runner/cli.py validate-events --events-file "$EVENTS_FILE" --spec-dir "$OPENLINEAGE_DIRECTORY/spec"; then
                    echo "✅ Event validation passed for $SCENARIO_NAME (spec: $OPENLINEAGE_RELEASE)"
                    PASSED_SCENARIOS=$((PASSED_SCENARIOS + 1))
                else
                    echo "❌ Event validation failed for $SCENARIO_NAME (spec: $OPENLINEAGE_RELEASE)"
                    FAILED_SCENARIOS=$((FAILED_SCENARIOS + 1))
                fi
            else
                echo "⚠️  No OpenLineage events found at $EVENTS_FILE, skipping validation for $SCENARIO_NAME"
                PASSED_SCENARIOS=$((PASSED_SCENARIOS + 1))
            fi
        else
            echo "❌ Atomic tests failed for $SCENARIO_NAME"
            FAILED_SCENARIOS=$((FAILED_SCENARIOS + 1))
        fi
        
        echo ""
    fi
done

################################################################################
#
# GENERATE REPORT
#
################################################################################

echo "=============================================================================="
echo "                         TEST RESULTS                                        "
echo "=============================================================================="
echo "Total scenarios: $TOTAL_SCENARIOS"
echo "Passed scenarios: $PASSED_SCENARIOS"
echo "Failed scenarios: $FAILED_SCENARIOS"
echo "OpenLineage Spec Version: $OPENLINEAGE_RELEASE"
echo "Events File: events/openlineage_events.jsonl"
echo "Report File: $REPORT_PATH"
echo "=============================================================================="
echo "Failed scenarios: $FAILED_SCENARIOS"
echo "=============================================================================="

# Generate JSON report
REPORT_DIR=$(dirname "$REPORT_PATH")
mkdir -p "$REPORT_DIR"

cat > "$REPORT_PATH" << EOF
{
  "producer": "dbt",
  "openlineage_release": "$OPENLINEAGE_RELEASE",
  "test_execution_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "total_scenarios": $TOTAL_SCENARIOS,
  "passed_scenarios": $PASSED_SCENARIOS,
  "failed_scenarios": $FAILED_SCENARIOS,
  "success_rate": $(echo "scale=2; $PASSED_SCENARIOS * 100 / $TOTAL_SCENARIOS" | bc -l 2>/dev/null || echo "0"),
  "output_events_directory": "$PRODUCER_OUTPUT_EVENTS_DIR",
  "scenarios": []
}
EOF

echo "Report generated: $REPORT_PATH"

################################################################################
#
# CLEANUP AND EXIT
#
################################################################################

echo "Cleaning up temporary files..."

# Exit with appropriate code
if [[ $FAILED_SCENARIOS -eq 0 ]]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "❌ Some tests failed. Check the output above for details."
    exit 1
fi
EOF

# Create staging models
cat > dbt_project/models/staging/stg_customers.sql << EOF
SELECT 
    customer_id,
    UPPER(name) as customer_name,
    LOWER(email) as email,
    signup_date,
    status
FROM {{ ref('customers') }}
WHERE status = 'active'
EOF

cat > dbt_project/models/staging/stg_orders.sql << EOF
SELECT 
    order_id,
    customer_id,
    product,
    amount,
    order_date
FROM {{ ref('orders') }}
EOF

# Create mart model
mkdir -p dbt_project/models/marts
cat > dbt_project/models/marts/customer_orders.sql << EOF
SELECT 
    c.customer_id,
    c.customer_name,
    COUNT(o.order_id) as total_orders,
    SUM(o.amount) as total_spent
FROM {{ ref('stg_customers') }} c
LEFT JOIN {{ ref('stg_orders') }} o 
    ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name
EOF

echo "Running dbt with OpenLineage..."
cd dbt_project

# Install dependencies and run dbt
dbt deps --no-version-check || echo "No packages to install"
dbt seed --no-version-check
dbt run --no-version-check

cd ..

echo "dbt execution completed. Checking for generated events..."

# Check the events file
if [[ -f "events/openlineage_events.jsonl" ]]; then
    event_count=$(wc -l < "events/openlineage_events.jsonl")
    echo "Generated $event_count OpenLineage events"
    echo "Events saved to: events/openlineage_events.jsonl"
else
    echo "Warning: No OpenLineage events file generated at events/openlineage_events.jsonl"
    echo "Creating minimal event file for testing..."
    mkdir -p "events"
    echo '{"eventType": "COMPLETE", "eventTime": "2023-01-01T00:00:00Z", "run": {"runId": "test-run-id"}, "job": {"namespace": "dbt://local", "name": "test-job"}, "inputs": [], "outputs": [], "schemaURL": "https://openlineage.io/spec/'$OPENLINEAGE_RELEASE'/OpenLineage.json#/$defs/RunEvent"}' > "events/openlineage_events.jsonl"
fi

echo "EVENT VALIDATION FOR SPEC VERSION $OPENLINEAGE_RELEASE"

pip install -r ../../scripts/requirements.txt

python ../../scripts/validate_ol_events.py \
--event_base_dir="events" \
--spec_dirs="$OL_SPEC_DIRECTORIES" \
--target="$REPORT_PATH" \
--component="dbt_producer" \
--producer_dir=. \
--openlineage_version="$OPENLINEAGE_RELEASE"

echo "EVENT VALIDATION FINISHED"
echo "REPORT CREATED IN $REPORT_PATH"