#!/bin/bash

# Define base path (you can modify this if you want to use a different root directory)
BASE_PATH="${1:-.}"

# Initialize missing count
missing_count=0

# Function to check if a path exists
check_path() {
    local path="$1"
    if [[ ! -e "$path" ]]; then
        echo "Missing: $path"
        missing_count=$((missing_count + 1))
    fi
}

# Function to remove trailing slashes from a directory path
remove_trailing_slash() {
    echo "${1%/}"
}

# Check for static files in base paths
check_path "$BASE_PATH/consumer/README.md"
check_path "$BASE_PATH/generated-files/compatibility-table.md"
check_path "$BASE_PATH/generated-files/releases.json"
check_path "$BASE_PATH/generated-files/report.json"
check_path "$BASE_PATH/generated-files/spec_versions.json"

# Check all consumer structures
for consumer_dir in "$BASE_PATH/consumer/consumers/"*/; do
    consumer_dir=$(remove_trailing_slash "$consumer_dir")
    [[ -d "$consumer_dir" ]] || continue  # Skip if not a directory

    check_path "$consumer_dir/README.md"
    check_path "$consumer_dir/maintainers.json"
    check_path "$consumer_dir/mapping.json"

    # Check each scenario inside the consumer
    for scenario_dir in "$consumer_dir/scenarios/"*/; do
        scenario_dir=$(remove_trailing_slash "$scenario_dir")
        [[ -d "$scenario_dir" ]] || continue

        check_path "$scenario_dir/config.json"
        check_path "$scenario_dir/maintainers.json"
        check_path "$scenario_dir/scenario.md"
        check_path "$scenario_dir/validation"
    done
done

# Check consumer-level scenarios (outside specific consumers)
for scenario_dir in "$BASE_PATH/consumer/scenarios/"*/; do
    scenario_dir=$(remove_trailing_slash "$scenario_dir")
    [[ -d "$scenario_dir" ]] || continue

    check_path "$scenario_dir/maintainers.json"
    check_path "$scenario_dir/scenario.md"

    # Check if at least one event file is present
    if ! compgen -G "$scenario_dir/events/"*.json > /dev/null; then
        echo "Missing event JSON files in $scenario_dir/events/"
        missing_count=$((missing_count + 1))
    fi
done

# Check all producer structures
for producer_dir in "$BASE_PATH/producer/"*/; do
    producer_dir=$(remove_trailing_slash "$producer_dir")
    [[ -d "$producer_dir" ]] || continue

    check_path "$producer_dir/README.md"
    check_path "$producer_dir/maintainers.json"
    check_path "$producer_dir/runner"

    # Generate the run script path using directory name without double slashes
    producer_name=$(basename "$producer_dir")
    check_path "$producer_dir/run_${producer_name}_tests.sh"

    # Check each scenario inside the producer
    for scenario_dir in "$producer_dir/scenarios/"*/; do
        scenario_dir=$(remove_trailing_slash "$scenario_dir")
        [[ -d "$scenario_dir" ]] || continue

        check_path "$scenario_dir/config.json"
        check_path "$scenario_dir/maintainers.json"
        check_path "$scenario_dir/scenario.md"

        # Check if at least one event file is present
        if ! compgen -G "$scenario_dir/events/"*.json > /dev/null; then
            echo "Missing event JSON files in $scenario_dir/events/"
            missing_count=$((missing_count + 1))
        fi
    done
done

# Summary of results
if [[ $missing_count -eq 0 ]]; then
    exit 0
else
    echo "$missing_count required paths are missing."
    exit 1
fi
