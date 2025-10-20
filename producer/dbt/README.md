# dbt Producer Compatibility Test

## Purpose and Scope

This directory contains a compatibility test for the `openlineage-dbt` integration. Its purpose is to provide a standardized and reproducible framework for validating that dbt's OpenLineage integration produces events compliant with the OpenLineage specification.

This framework is designed as a reference for the community to:
-   Verify that `dbt-ol` generates syntactically and semantically correct OpenLineage events for common dbt operations.
-   Provide a consistent testing environment for `openlineage-dbt` across different versions.
-   Serve as a foundation for more advanced testing scenarios, such as multi-spec or multi-implementation validation.

It is important to note that this is a **compatibility validation framework** using synthetic data. It is not intended to be a demonstration of a production data pipeline.

## Test Architecture and Workflow

The test is orchestrated by the `run_dbt_tests.sh` script and follows a clear, sequential workflow designed for reliability and ease of use. This structure ensures that each component of the integration is validated systematically.

The end-to-end process is as follows:

1.  **Test Orchestration**: The `run_dbt_tests.sh` script serves as the main entry point. It sets up the environment and initiates the Python-based test runner (`test_runner/cli.py`).

2.  **Scenario Execution**: The test runner executes the dbt project defined in the `runner/` directory. The specific dbt commands to be run (e.g., `dbt seed`, `dbt run`, `dbt test`) are defined in the test scenarios located under `scenarios/`.

3.  **Event Generation and Capture**: During the execution, the `dbt-ol` wrapper intercepts the dbt commands and emits OpenLineage events. The `runner/openlineage.yml` configuration directs these events to be captured as a local file (`events/openlineage_events.jsonl`) using the `file` transport.

4.  **Event Validation**: Once the dbt process is complete, the test framework performs a two-stage validation on the generated `openlineage_events.jsonl` file:
    *   **Syntax Validation**: Each event is validated against the official OpenLineage JSON schema (e.g., version `2-0-2`) to ensure it is structurally correct.
    *   **Semantic Validation**: The content of the events is compared against expected templates. This deep comparison, powered by the `scripts/compare_events.py` utility, verifies the accuracy of job names, dataset identifiers, lineage relationships, and the presence and structure of key facets.

5.  **Reporting**: Upon completion, the test runner generates a standardized JSON report (`dbt_producer_report.json`) that details the results of each validation step. This report is designed to be consumed by higher-level aggregation scripts in a CI/CD environment.

## Validation Scope

This test validates that the `openlineage-dbt` integration correctly generates OpenLineage events for core dbt operations.

#### dbt Operations Covered:
-   `dbt seed`: To load initial data.
-   `dbt run`: To execute dbt models.
-   `dbt test`: To run data quality tests.

#### Validation Checks:
-   **Event Generation**: Correctly creates `START` and `COMPLETE` events for jobs and runs.
-   **Core Facet Structure and Content**: Validates key facets, including:
    -   `jobType`
    -   `sql`
    -   `processing_engine`
    -   `parent` (for job/run relationships)
    -   `dbt_run`, `dbt_version`
    -   `schema`, `dataSource`
    -   `documentation`
    -   `columnLineage`
    -   `dataQualityAssertions` (for dbt tests)
-   **Specification Compliance**: Events are validated against the OpenLineage specification schema (version `2-0-2`).

A detailed, facet-by-facet analysis of specification coverage is available in `SPECIFICATION_COVERAGE_ANALYSIS.md`.

## Test Structure

The test is organized into the following key directories, each with a specific role in the validation process:

```
producer/dbt/
├── run_dbt_tests.sh           # Main test execution script
├── test_runner/               # Python test framework for orchestration and validation
├── scenarios/                 # Defines the dbt commands and expected outcomes for each test case
├── events/                    # Default output directory for generated OpenLineage events
├── runner/                    # A self-contained dbt project used as the test target
└── future/                    # Design documents for future enhancements
```

-   **`runner/`**: A self-contained dbt project with models, seeds, and configuration. This is the target of the `dbt-ol` command.
-   **`scenarios/`**: Defines the dbt commands to be executed and contains the expected event templates for validation.
-   **`test_runner/`**: A custom Python application that orchestrates the end-to-end test workflow. It uses the `click` library to provide a command-line interface, execute the dbt process, and trigger the validation of the generated OpenLineage events.
-   **`events/`**: The default output directory for the generated `openlineage_events.jsonl` file.

## How to Run the Tests

To execute the test suite, you will need a local clone of the main [OpenLineage repository](https://github.com/OpenLineage/OpenLineage), as the validation tool requires access to the specification files.

### Prerequisites

1.  **Install Python Dependencies**:
    ```bash
    # From the producer/dbt/ directory
    pip install -r test_runner/requirements.txt
    ```

2.  **Install dbt and the DuckDB adapter**:
    ```bash
    pip install dbt-core dbt-duckdb
    ```

3.  **Install the OpenLineage dbt integration**:
    ```bash
    pip install openlineage-dbt
    ```

### Execution

Run the main test script, providing the path to your local OpenLineage repository.

#### Basic Example
This command runs the test suite with default settings, validating against the `2-0-2` OpenLineage release and saving events to the `events/` directory.

```bash
# Example assuming the OpenLineage repo is cloned in a sibling directory
./run_dbt_tests.sh --openlineage-directory ../OpenLineage
```

#### Full Example
This command demonstrates how to override the default settings by specifying all available arguments.

```bash
./run_dbt_tests.sh \
  --openlineage-directory /path/to/your/OpenLineage \
  --producer-output-events-dir /tmp/dbt_events \
  --openlineage-release 2-0-2 \
  --report-path /tmp/dbt_report.json
```

### Command-Line Arguments
-   `--openlineage-directory` (**Required**): Path to the root of a local clone of the OpenLineage repository, which contains the `spec/` directory.
-   `--producer-output-events-dir`: Directory where generated OpenLineage events will be saved. (Default: `events/`)
-   `--openlineage-release`: The OpenLineage release version to validate against. (Default: `2-0-2`)
-   `--report-path`: Path where the final JSON test report will be generated. (Default: `../dbt_producer_report.json`)

## Important dbt Integration Notes

**⚠️ Please review the [OpenLineage dbt documentation](https://openlineage.io/docs/integrations/dbt) before running tests.**

This integration has several nuances that are important to understand when analyzing test results or extending the framework:

-   The `dbt-ol` wrapper has specific configuration requirements that differ from a standard `dbt` execution.
-   Event emission timing can vary depending on the dbt command being run (`run`, `test`, `build`).
-   The availability of certain dbt-specific facets may depend on the version of `dbt-core` being used.
-   The file transport configuration in `openlineage.yml` directly controls the location and format of the event output.

## Future Enhancements

To support community discussions around forward and backward compatibility, the `future/` directory contains design documents exploring a potential approach to multi-spec and multi-implementation version testing.

These documents outline a methodology for testing a single producer implementation against multiple versions of the OpenLineage specification and client libraries. We hope these ideas can serve as a useful starting point for this important conversation within the OpenLineage community.

See `future/README.md` for more details.

## Maintainers

**Maintainer**: BearingNode Team
**Contact**: contact@bearingnode.com
**Website**: https://www.bearingnode.com
