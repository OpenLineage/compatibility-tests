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
├── runner/                    # A self-contained dbt project used as the test target, and run_scenarios.sh
├── run_dbt_tests.sh           # Runs the scenarios locally, as CI does
├── versions.json              # Supported component and OpenLineage version ranges
└── maintainers.json           # Maintainer contact information
```

-   **`runner/`**: A self-contained dbt project with models, seeds, and configuration. This is the target of the `dbt-ol` command. `runner/run_scenarios.sh` runs the scenarios and records how each ended in `status.json`; CI and `run_dbt_tests.sh` both call it.
-   **`scenarios/`**: Contains one directory per scenario. Each scenario has a `config.json` defining expected event templates, an `events/` directory of expected event JSON files, and a `test/` directory with `run.sh` and `compose.yml`.

## How to Run the Tests

The dbt tests run in GitHub Actions on every pull request that touches them and in the scheduled release check. You can run them on your machine the same way (see [Run locally, as CI does](#run-locally-as-ci-does)); both use the same scripts.

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
- Runs the scenarios valid for the versions with `runner/run_scenarios.sh`
- Validates events against OpenLineage JSON schemas
- Generates compatibility reports and uploads artifacts

**Configuration**: See `.github/workflows/producer_dbt.yml` for the complete workflow definition.

---

### Run locally, as CI does

Use this to test a new or changed scenario before you commit it. Locally, the steps and scripts are the same as in
`.github/workflows/producer_dbt.yml`. Only the Postgres is different: CI uses a service container, locally the scenario's
`test/run.sh` starts the same `postgres:15-alpine` with Docker Compose if nothing is listening on `localhost:5432`.

**Prerequisites:** Python 3.11+ (CI uses 3.12), `jq`, `git` and Docker. No GCP access is needed.

**Pick the versions** from `producer/dbt/versions.json` (`component_version`; OpenLineage: the latest release, or the one
you're testing). Scenarios only run for the versions in their `config.json`.

#### One command

From the repository root:

```bash
producer/dbt/run_dbt_tests.sh --component-version 1.8.0 --openlineage-version 1.55.0
```

Options: `--scenarios 'csv_to_postgres'` runs only the given scenarios, `--events-dir` and `--report-dir` move the output
(`--help` lists everything). The first run creates a virtualenv with `dbt-core==1.8.0`, `dbt-postgres` and
`openlineage-dbt==1.55.0` in `~/.cache/openlineage-compatibility-tests/venvs/` and clones OpenLineage for the spec; later
runs reuse both.

#### The same steps by hand

One command per CI step, so you can stop after any of them, look at the output, or re-run just one:

```bash
V=1.8.0 OL=1.55.0 EVENTS=$PWD/dbt-events-$V-$OL

# "Initialize tests": the scenarios valid for the versions
SCENARIOS=$(scripts/get_valid_test_scenarios.sh producer/dbt/scenarios $V $OL); echo "$SCENARIOS"

# "Install dbt dependencies" (any virtualenv outside the repo)
python3 -m venv ~/.venvs/dbt-$V-$OL
~/.venvs/dbt-$V-$OL/bin/pip install dbt-core==$V dbt-postgres openlineage-dbt==$OL

# "Run dbt scenarios and create OL events"
PATH=~/.venvs/dbt-$V-$OL/bin:$PATH producer/dbt/runner/run_scenarios.sh --events-dir "$EVENTS" --scenarios "$SCENARIOS"

# "Validation"
dev/validation/validate_locally.sh --component dbt --component-version $V --openlineage-version $OL --events-dir "$EVENTS"
```

#### What you get

- `dbt-events-<V>-<OL>/<scenario>/event-N.json`: the events, one file per event, in the order dbt-ol emitted them.
- `dbt-events-<V>-<OL>/status.json`: how each scenario's run ended (`DONE` or `FAILED`). A `FAILED` scenario fails validation
  with a "producer job" test; the dbt output above it shows why.
- `dbt-<V>-<OL>-report.json`: the report, with the same name and format as the CI artifact. The script prints a line per
  scenario with its status and the tests that didn't pass, and exits 1 if a scenario failed. A test that doesn't match its
  expected event lists the differences in its `details`:

  ```bash
  jq '.[].scenarios[] | {name, status, failed: [.tests[] | select(.status == "FAILURE") | {name, details}]}' dbt-1.8.0-1.55.0-report.json
  ```

Both outputs are git-ignored when they're in the repository root. The Postgres container keeps running after the run;
stop it with `docker compose -f producer/dbt/scenarios/csv_to_postgres/test/compose.yml down -v` (`-v` also drops the data).

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
