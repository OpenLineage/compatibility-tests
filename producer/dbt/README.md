# dbt Producer Compatibility Test

## Purpose and Scope

This directory contains a compatibility test for the `openlineage-dbt` integration. Its purpose is to provide a standardized and reproducible framework for validating that dbt's OpenLineage integration produces events compliant with the OpenLineage specification.

This framework is designed as a reference for the community to:
-   Verify that `dbt-ol` generates syntactically and semantically correct OpenLineage events for common dbt operations.
-   Provide a consistent testing environment for `openlineage-dbt` across different versions.
-   Serve as a foundation for more advanced testing scenarios, such as multi-spec or multi-implementation validation.

It is important to note that this is a **compatibility validation framework** using synthetic data. It is not intended to be a demonstration of a production data pipeline.

## Test Architecture and Workflow

The test is orchestrated by the scenario's `test/run.sh` script and follows a clear, sequential workflow designed for reliability and ease of use. This structure ensures that each component of the integration is validated systematically.

The end-to-end process is as follows:

1.  **Scenario Execution**: The `test/run.sh` script executes the dbt project defined in the `runner/` directory using `dbt-ol seed`, `dbt-ol run`, and `dbt-ol test`.

2.  **Event Generation and Capture**: During the execution, the `dbt-ol` wrapper intercepts the dbt commands and emits OpenLineage events. The `test/run.sh` script writes an `openlineage.yml` configuration that directs these events to be captured as a local file (`{output_dir}/events.jsonl`) using the `file` transport.
 
3.  **Extract events**: OpenLineage emits all events to one file, so `run.sh` splits them into individual numbered files (`event-1.json`, `event-2.json`, …) before deleting the combined `.jsonl`.

4.  **Event Validation**: Once the dbt process is complete, the shared framework (`scripts/validate_ol_events.py`) performs a two-stage validation on the generated events:
    *   **Syntax Validation**: Each event is validated against the official OpenLineage JSON schema to ensure it is structurally correct.
    *   **Semantic Validation**: The content of the events is compared against expected templates in `scenarios/csv_to_postgres/events/`. This comparison, powered by the `scripts/compare_events.py` utility, verifies the accuracy of job names, dataset identifiers, lineage relationships, and the presence and structure of key facets.

5.  **Reporting**: Upon completion, the framework generates a standardised JSON report that details the results of each validation step for consumption by CI/CD aggregation scripts.

## Validation Scope

This test validates that the `openlineage-dbt` integration correctly generates OpenLineage events for core dbt operations.

#### dbt Operations Covered:
-   `dbt seed`: To load initial data.
-   `dbt run`: To execute dbt models.
-   `dbt test`: To run data quality tests and capture `dataQualityAssertions` facets.

#### Validation Checks:
-   **Event Generation**: Correctly creates `START` and `COMPLETE` events for jobs and runs.
-   **Core Facet Structure and Content**: Validates key facets, including:
    -   `jobType`
    -   `sql`
    -   `dbt_run`
    -   `dbt_version`
    -   `dbt_node`
    -   `schema`
    -   `dataSource`
    -   `columnLineage`
    -   `dataQualityAssertions`
-   **Specification Compliance**: Events are validated against the OpenLineage specification schema (version `2-0-2`).

## Test Structure

The test is organized into the following key directories, each with a specific role in the validation process:

```
producer/dbt/
├── scenarios/                 # Test scenarios; each defines expected events and a run script
├── runner/                    # A self-contained dbt project used as the test target
├── versions.json              # Supported component and OpenLineage version ranges
└── maintainers.json           # Maintainer contact information
```

-   **`runner/`**: A self-contained dbt project with models, seeds, and configuration. This is the target of the `dbt-ol` command.
-   **`scenarios/`**: Contains one directory per scenario. Each scenario has a `config.json` defining expected event templates, an `events/` directory of expected event JSON files, and a `test/` directory with `run.sh` and `compose.yml`.

## How to Run the Tests

There are two primary ways to run the dbt compatibility tests: **locally for development and debugging**, or via **GitHub Actions for automated CI/CD validation**. Both approaches use the same underlying test framework but differ in their database setup and execution environment.

### Running Tests via GitHub Actions (Automated CI/CD)

**This is the standard, automated test runner for the repository and community.**

GitHub Actions provides the canonical testing environment with:
- PostgreSQL 15 service container (automatically provisioned)
- Matrix testing across multiple dbt and OpenLineage versions
- Automated event validation against OpenLineage specifications
- Integration with the repository's reporting and compatibility tracking

#### Triggering GitHub Actions Workflows

1. **Automatic Trigger on Pull Requests**: The workflow runs automatically when changes are detected in `producer/dbt/` paths.

2. **Via Pull Request**: Opening a PR that modifies dbt producer files will automatically trigger the test suite.

The GitHub Actions workflow:
- Provisions a PostgreSQL 15 container with health checks
- Installs `dbt-core`, `dbt-postgres`, and `openlineage-dbt` at specified versions
- Executes all scenarios defined in `scenarios/`
- Validates events against OpenLineage JSON schemas
- Generates compatibility reports and uploads artifacts

**Configuration**: See `.github/workflows/producer_dbt.yml` for the complete workflow definition.

---

### Local Debugging (Optional)

**For development debugging, local runs should use the same PostgreSQL 15 Docker setup as CI.**

If you need to debug event generation locally:

1.  **Ensure Docker is available**:
    - The scenario runner will start the local Docker Compose Postgres service automatically if it is not already reachable on `localhost:5432`.

2.  **Install dbt and the OpenLineage wrapper** (use a virtual environment outside the repo):
    ```bash
    python -m venv ~/.venvs/dbt-compat-test
    source ~/.venvs/dbt-compat-test/bin/activate
    pip install dbt-core==1.8.0 dbt-postgres openlineage-dbt==1.23.0
    ```
    
3.  **Run the dbt producer test harness**:
    - Run this from the repository root so the default output paths resolve correctly.
    ```bash
    ./producer/dbt/run_dbt_tests.sh \
      --openlineage-directory /path/to/OpenLineage \
      --producer-output-events-dir ./producer/dbt/output \
      --openlineage-release 1.45.0 \
      --report-path ./dbt_producer_report.json
    ```

4.  **Inspect generated events**:
    ```bash
    cat ./producer/dbt/output/csv_to_postgres/event-{id}.json | jq '.'
    cat ./dbt_producer_report.json | jq '.'
    ```

**Note**: Local debugging is entirely optional. All official validation happens in GitHub Actions with PostgreSQL service containers. The `run_dbt_tests.sh` wrapper uses the same scenario scripts and validation pipeline as CI, including the merged local test-aid improvements from #283.

## Important dbt Integration Notes

**⚠️ Please review the [OpenLineage dbt documentation](https://openlineage.io/docs/integrations/dbt) before running tests.**

This integration has several nuances that are important to understand when analyzing test results or extending the framework:

-   The `dbt-ol` wrapper has specific configuration requirements that differ from a standard `dbt` execution.
-   Event emission timing can vary depending on the dbt command being run (`run`, `test`, `build`).
-   The availability of certain dbt-specific facets may depend on the version of `dbt-core` being used.
-   The file transport configuration in `openlineage.yml` directly controls the location and format of the event output.

## ⚠️ Known Validation Issues

The dbt integration emits facets for which we cannot apply syntax validation due to schema issues:

### Custom dbt Facets:
1. **`dbt_version`** (Run Facet)
    - **Purpose**: Captures the version of dbt-core being used
    - **Schema**: `dbt-version-run-facet.json`
    - **Example**: `{"version": "1.10.15"}`
    - **Schema issues**:
        - lack of the '$id' property
        - lack of the 'properties' object
        - wrong ref to the RunFacet definition: OpenLineage.json#/**definitions**/RunFacet instead of OpenLineage.json#/**$defs**/RunFacet

2. **`dbt_run`** (Run Facet)
    - **Purpose**: Captures dbt-specific execution metadata
    - **Schema**: `dbt-run-run-facet.json`
    - **Fields**: `dbt_runtime`, `invocation_id`, `profile_name`, `project_name`, `project_version`
    - **Schema issues**:
        - wrong type definition: "type": "**str**" instead of "type": "**string**"
        - wrong ref to the RunFacet definition: OpenLineage.json#/**definitions**/RunFacet instead of OpenLineage.json#/**$defs**/RunFacet
