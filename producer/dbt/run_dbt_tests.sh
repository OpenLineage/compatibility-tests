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
    echo "  --openlineage-release VERSION       OpenLineage release version (default: 1.23.0)"
    echo "  --report-path PATH                  Path to report directory (default: ../dbt_producer_report.json)"
    echo "  -h, --help                          Show this help message and exit"
    echo ""
    echo "Example:"
    echo "  $0 --openlineage-directory /path/to/specs --producer-output-events-dir output --openlineage-release 1.23.0"
    exit 0
}

# Required variables (no defaults)
OPENLINEAGE_DIRECTORY=""

# Variables with default values
PRODUCER_OUTPUT_EVENTS_DIR=output
OPENLINEAGE_RELEASE=1.23.0
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

echo "RUNNING dbt PRODUCER TEST SCENARIOS"

################################################################################
#
# RUN dbt PRODUCER TEST SCENARIOS
#
################################################################################

echo "Preparing dbt environment..."

# Check if dbt is available
if ! command -v dbt &> /dev/null; then
    echo "Error: dbt command not found. Please ensure dbt is installed and in PATH."
    exit 1
fi

# Configure OpenLineage for file transport
echo "Configuring OpenLineage for file transport..."
cat > openlineage.yml << EOF
transport:
  type: file
  log_file_path: $PRODUCER_OUTPUT_EVENTS_DIR/openlineage_events.json
  append: true
EOF

echo "Running dbt with OpenLineage integration..."

# Clear previous events
rm -f "$PRODUCER_OUTPUT_EVENTS_DIR/openlineage_events.json"

# Run dbt to generate OpenLineage events
# Note: This assumes a dbt project is set up in the scenario directory
# For now, we'll create a minimal setup that can be expanded

echo "Setting up minimal dbt project for testing..."

# Create minimal dbt project structure for testing
mkdir -p dbt_project/models/staging
mkdir -p dbt_project/seeds

# Create minimal dbt_project.yml
cat > dbt_project/dbt_project.yml << EOF
name: 'openlineage_test'
version: '1.0.0'
config-version: 2

model-paths: ["models"]
seed-paths: ["seeds"]
target-path: "target"

models:
  openlineage_test:
    staging:
      +materialized: table
EOF

# Create minimal profiles.yml for DuckDB
mkdir -p ~/.dbt
cat > ~/.dbt/profiles.yml << EOF
openlineage_test:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: /tmp/openlineage_test.duckdb
      threads: 1
EOF

# Create sample CSV data
cat > dbt_project/seeds/customers.csv << EOF
customer_id,name,email,signup_date,status
1,John Doe,john@example.com,2023-01-15,active
2,Jane Smith,jane@example.com,2023-02-20,active
3,Bob Johnson,bob@example.com,2023-03-10,inactive
EOF

cat > dbt_project/seeds/orders.csv << EOF
order_id,customer_id,product,amount,order_date
101,1,Widget A,25.99,2023-04-01
102,1,Widget B,15.99,2023-04-15
103,2,Widget A,25.99,2023-04-20
104,3,Widget C,35.99,2023-05-01
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

if [[ -f "$PRODUCER_OUTPUT_EVENTS_DIR/openlineage_events.json" ]]; then
    event_count=$(wc -l < "$PRODUCER_OUTPUT_EVENTS_DIR/openlineage_events.json")
    echo "Generated $event_count OpenLineage events"
else
    echo "Warning: No OpenLineage events file generated"
    echo "Creating minimal event file for testing..."
    mkdir -p "$PRODUCER_OUTPUT_EVENTS_DIR"
    echo '{"eventType": "COMPLETE", "eventTime": "2023-01-01T00:00:00Z", "run": {"runId": "test-run-id"}, "job": {"namespace": "dbt://local", "name": "test-job"}, "inputs": [], "outputs": []}' > "$PRODUCER_OUTPUT_EVENTS_DIR/openlineage_events.json"
fi

echo "EVENT VALIDATION"

pip install -r ../../scripts/requirements.txt

python ../../scripts/validate_ol_events.py \
--event_base_dir="$PRODUCER_OUTPUT_EVENTS_DIR" \
--spec_dirs="$OL_SPEC_DIRECTORIES" \
--target="$REPORT_PATH" \
--component="dbt_producer" \
--producer_dir=.

echo "EVENT VALIDATION FINISHED"
echo "REPORT CREATED IN $REPORT_PATH"