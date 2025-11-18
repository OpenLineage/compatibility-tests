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

**For detailed coverage analysis**, see **[`SPECIFICATION_COVERAGE_ANALYSIS.md`](./SPECIFICATION_COVERAGE_ANALYSIS.md)** which provides:
- Comprehensive facet-by-facet coverage breakdown (39% overall specification coverage)
- Detailed explanation of custom dbt facets and validation warnings
- Analysis of what's tested vs. what's not tested and why
- Recommendations for future coverage improvements
- Resolution status for known validation warnings

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

2. **Manual Trigger via Workflow Dispatch**:
   ```bash
   # Trigger for specific branch
   gh workflow run main_pr.yml --ref feature/your-branch -f components="dbt"
   
   # Watch the run
   gh run watch
   ```

3. **Via Pull Request**: Opening a PR that modifies dbt producer files will automatically trigger the test suite.

The GitHub Actions workflow:
- Provisions a PostgreSQL 15 container with health checks
- Installs `dbt-core`, `dbt-postgres`, and `openlineage-dbt` at specified versions
- Executes all scenarios defined in `scenarios/`
- Validates events against OpenLineage JSON schemas
- Generates compatibility reports and uploads artifacts

**Configuration**: See `.github/workflows/producer_dbt.yml` for the complete workflow definition.

---

### Running Tests Locally (Development & Debugging)

**Use this approach for iterative development, debugging, and testing changes before pushing to GitHub.**

Local testing provides:
- Faster feedback loops for development
- Direct access to event files and logs
- Ability to inspect database state
- Control over specific test scenarios

#### Prerequisites

1.  **Start PostgreSQL Container**:
    ```bash
    # From the producer/dbt/ directory
    docker-compose up -d
    
    # Verify container is healthy
    docker-compose ps
    ```

2.  **Install Python Dependencies**:
    ```bash
    # Activate virtual environment (recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    
    # Install requirements
    pip install -r test_runner/requirements.txt
    ```

3.  **Install dbt and the PostgreSQL adapter**:
    ```bash
    pip install dbt-core dbt-postgres
    ```

4.  **Install the OpenLineage dbt integration**:
    ```bash
    pip install openlineage-dbt
    ```

5.  **Verify dbt Connection**:
    ```bash
    cd runner/
    dbt debug
    cd ..
    ```

#### Local Execution Options

**Option 1: Using the Test Runner CLI (Recommended)**

The test runner CLI provides the same orchestration used in GitHub Actions:

```bash
# Run a specific scenario
python test_runner/cli.py run-scenario \
  --scenario csv_to_postgres_local \
  --output-dir ./test_output/$(date +%s)

# List available scenarios
python test_runner/cli.py list-scenarios
```

**Option 2: Direct dbt-ol Execution (For debugging)**

For fine-grained control and debugging, run `dbt-ol` commands directly:

```bash
cd runner/

# Generate events for seed operation
dbt-ol seed

# Generate events for model execution
dbt-ol run

# Generate events for tests
dbt-ol test

# Inspect generated events
cat ../events/openlineage_events.jsonl | jq '.'
```

**Option 3: Legacy Shell Script (Deprecated)**

The `run_dbt_tests.sh` script is deprecated but still available:

```bash
./run_dbt_tests.sh \
  --openlineage-directory /path/to/OpenLineage \
  --producer-output-events-dir ./events \
  --openlineage-release 2-0-2 \
  --report-path ./dbt_report.json
```

#### Local vs. GitHub Actions: Key Differences

| Aspect | Local Testing | GitHub Actions |
|--------|---------------|----------------|
| **Database** | Docker Compose (manual start) | PostgreSQL service container (auto-provisioned) |
| **Environment** | Uses local environment variables from `profiles.yml` | Uses workflow-defined environment variables |
| **Event Output** | Writes to `events/openlineage_events.jsonl` by default | Writes to temporary directory defined by workflow |
| **Validation** | Manual inspection or via test runner CLI | Automated validation against OpenLineage schemas |
| **Use Case** | Development, debugging, local verification | CI/CD, PR validation, compatibility reporting |
| **Cleanup** | Manual (`docker-compose down -v`) | Automatic container cleanup |

#### Cleaning Up Local Environment

```bash
# Stop PostgreSQL container
docker-compose down

# Remove PostgreSQL data volume (clean slate)
docker-compose down -v

# Remove generated event files
rm -rf events/*.jsonl test_output/
```

---

### Command-Line Arguments (Legacy Script)

For the deprecated `run_dbt_tests.sh` script:

-   `--openlineage-directory` (**Required**): Path to a local clone of the OpenLineage repository
-   `--producer-output-events-dir`: Directory for generated OpenLineage events (Default: `events/`)
-   `--openlineage-release`: OpenLineage release version to validate against (Default: `2-0-2`)
-   `--report-path`: Path for the final JSON test report (Default: `../dbt_producer_report.json`)

## Important dbt Integration Notes

**⚠️ Please review the [OpenLineage dbt documentation](https://openlineage.io/docs/integrations/dbt) before running tests.**

This integration has several nuances that are important to understand when analyzing test results or extending the framework:

-   The `dbt-ol` wrapper has specific configuration requirements that differ from a standard `dbt` execution.
-   Event emission timing can vary depending on the dbt command being run (`run`, `test`, `build`).
-   The availability of certain dbt-specific facets may depend on the version of `dbt-core` being used.
-   The file transport configuration in `openlineage.yml` directly controls the location and format of the event output.

### Custom dbt Facets and Validation Warnings

**The dbt integration emits custom facets that generate expected validation warnings:**

The `openlineage-dbt` integration adds vendor-specific facets to OpenLineage events that are **not part of the official OpenLineage specification**:

1. **`dbt_version`** - Captures the dbt-core version
2. **`dbt_run`** - Captures dbt execution metadata (invocation_id, profile_name, project_name, etc.)

These facets:
- ✅ Have valid schema definitions in the OpenLineage repository
- ✅ Provide valuable dbt-specific context for lineage consumers
- ⚠️ Generate validation warnings: `"facet type dbt_version not recognized"` and `"facet type dbt_run not recognized"`
- ℹ️ Are **expected behavior** for vendor-specific OpenLineage extensions

**Impact on Test Results:**
- All dbt operations complete successfully (seed, run, test)
- All events are generated with correct OpenLineage structure
- Core facets (schema, dataSource, sql, columnLineage, etc.) validate successfully
- Custom dbt facets trigger warnings during schema validation but do **not indicate test failure**

These warnings are **documented and accepted** as expected behavior. 

**📊 For complete technical details**, see **[`SPECIFICATION_COVERAGE_ANALYSIS.md`](./SPECIFICATION_COVERAGE_ANALYSIS.md)** which documents:
- The exact structure and purpose of `dbt_version` and `dbt_run` facets
- Why validation warnings occur (vendor extensions vs. official spec)
- Impact assessment on test results
- Current workarounds and long-term resolution options

## Future Enhancements

To support community discussions around forward and backward compatibility, the `future/` directory contains design documents exploring a potential approach to multi-spec and multi-implementation version testing.

These documents outline a methodology for testing a single producer implementation against multiple versions of the OpenLineage specification and client libraries. We hope these ideas can serve as a useful starting point for this important conversation within the OpenLineage community.

See `future/README.md` for more details.

## Maintainers

**Maintainer**: BearingNode Team
**Contact**: contact@bearingnode.com
**Website**: https://www.bearingnode.com
# Test workflow trigger
