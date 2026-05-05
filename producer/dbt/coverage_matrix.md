# dbt Producer Coverage Matrix

This document formalizes the minimum coverage expectations for the dbt producer compatibility tests across versions, facets, and scenarios. It separates implementation versions (dbt + openlineage-dbt) from OpenLineage specification versions and defines the baseline for test completeness.

## Version Coverage Policy

### 1) Implementation Versions (dbt-core + openlineage-dbt)

Implementation versions are the runtime versions of dbt and the OpenLineage dbt integration that generate events.

**Source of truth:**
- dbt version window: [producer/dbt/versions.json](producer/dbt/versions.json)
- CI inputs: [\.github/workflows/producer_dbt.yml](.github/workflows/producer_dbt.yml)

**Policy:**
- Maintain a rolling window of the most recent 2 dbt-core minor releases (N and N-1).
- For each dbt-core minor, test the latest available patch release in the window.
- Keep openlineage-dbt aligned to the OpenLineage release tag under test (the `ol_release` input).

**Current state:**
- dbt-core versions tested: 1.8.0 (only)
- openlineage-dbt is installed by CI for the specified `ol_release`

### 2) Specification Versions (OpenLineage JSON Schema)

Specification versions refer to the OpenLineage JSON schemas used to validate emitted events.

**Source of truth:**
- CI input `ol_release` in [\.github/workflows/producer_dbt.yml](.github/workflows/producer_dbt.yml)
- Scenario-level bounds in [producer/dbt/scenarios/csv_to_postgres/config.json](producer/dbt/scenarios/csv_to_postgres/config.json)

**Policy:**
- Validate events against a rolling window of the most recent 2 OpenLineage releases (N and N-1).
- Run cross-version checks so that each implementation version is validated against both spec versions in the window.

### 3) Cross-Version Matrix

The required matrix is:

- For each dbt-core version in window:
  - Validate against OpenLineage spec N
  - Validate against OpenLineage spec N-1

This ensures older implementations are validated against newer schemas and vice versa.

## Facet Coverage Baseline

Every dbt scenario defined in a `config.json` must validate these facets at minimum:

- `dataSource`
- `schema`
- `columnLineage`
- `sql`
- `dbt_node`
- `dbt_run`
- `dbt_version`

**Notes:**
- Core event structure is already validated by schema (eventType, job, run, inputs, outputs).
- Additional facets may be scenario-specific; they should be explicitly added to the scenario config when present.

## Scenario Coverage Baseline

A dbt compatibility suite is considered complete when it includes scenarios that cover:

- `seed` execution
- `run` execution (standard models)
- `incremental` model execution
- `test` execution
- `snapshot` execution

If a scenario covers multiple behaviors, it should list them in its scenario documentation and use event templates to validate them.

## Audit of Current Scenarios

| Scenario | seed | run | incremental | test | snapshot | Required facets baseline |
|----------|------|-----|-------------|------|----------|--------------------------|
| csv_to_postgres | yes | yes | no | no | no | yes |

### Gaps

- No scenario currently covers `incremental` models.
- No scenario currently covers `dbt test` execution.
- No scenario currently covers `dbt snapshot` execution.
- Only a single scenario exists; it does not represent a multi-scenario baseline.
