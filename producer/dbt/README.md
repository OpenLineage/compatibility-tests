# dbt Producer Compatibility Tests

## Description

This test validates dbt's OpenLineage integration compliance using a controlled testing environment. It uses synthetic data to test dbt's ability to generate compliant OpenLineage events, focusing on validation rather than representing production use cases.

## Purpose

**Primary Goal**: Validate that dbt + OpenLineage integration produces compliant events according to OpenLineage specification standards.

**What this is**: 
- A compatibility validation framework for dbt → OpenLineage integration
- A test harness using synthetic data to verify event generation compliance
- A reference implementation for testing dbt OpenLineage compatibility

**What this is NOT**:
- A production-ready data pipeline
- A real-world use case demonstration  
- Representative of typical production dbt implementations

## Test Architecture

**Test Pipeline**: Synthetic CSV → dbt Models → DuckDB  
**Transport**: Local file-based OpenLineage event capture  
**Validation**: Comprehensive facet compliance testing (schema, SQL, lineage, column lineage)

## Test Scenarios

### csv_to_duckdb_local

Controlled testing scenario with synthetic data that validates:
- dbt → OpenLineage integration functionality
- File transport event generation compliance
- Schema and SQL facet structural validation  
- Dataset and column lineage relationship accuracy

**Test Data**: Synthetic customer/order data designed for validation testing

## Running Tests

### Atomic Validation Tests
```bash
cd test_runner
python cli.py run-atomic --verbose
```

### Framework Validation Tests  
```bash
cd test_runner
python cli.py validate-events
```

### Complete Test Suite
```bash
./run_dbt_tests.sh --openlineage-directory /path/to/openlineage/specs
```

## Running Locally

To run dbt compatibility tests locally use the command:

```bash
./run_dbt_tests.sh \
  --openlineage-directory <path to your local openlineage repository containing spec> \
  --producer-output-events-dir <path where OpenLineage events will be saved> \
  --openlineage-release <OpenLineage release version> \
  --report-path <path where test report will be generated>
```

### Required Arguments
- `--openlineage-directory`: Path to local OpenLineage repository containing specifications

### Optional Arguments  
- `--producer-output-events-dir`: Directory for output events (default: `output`)
- `--openlineage-release`: OpenLineage version (default: `1.23.0`)
- `--report-path`: Test report location (default: `../dbt_producer_report.json`)

### Example
```bash
./run_dbt_tests.sh \
  --openlineage-directory /path/to/OpenLineage \
  --producer-output-events-dir ./output \
  --openlineage-release 1.23.0
```

## Prerequisites

1. **dbt**: Install dbt with DuckDB adapter
   ```bash
   pip install dbt-core dbt-duckdb
   ```

2. **OpenLineage dbt Integration**: Install the OpenLineage dbt package
   ```bash
   pip install openlineage-dbt
   ```

3. **Python Dependencies**: Install test runner dependencies
   ```bash
   cd test_runner
   pip install -r requirements.txt
   ```

4. **OpenLineage Configuration**: Review the [dbt integration documentation](https://openlineage.io/docs/integrations/dbt) for important configuration details and nuances when using the `dbt-ol` wrapper.

## OpenLineage Configuration

### Configuration File Location
The OpenLineage configuration is located at:
```
runner/openlineage.yml
```

This file configures:
- **Transport**: File-based event capture to the `events/` directory
- **Event Storage**: Where OpenLineage events are written
- **Schema Version**: Which OpenLineage specification version to use

### Event Output Location
Generated OpenLineage events are stored in:
```
events/openlineage_events.jsonl
```

Each line in this JSONL file contains a complete OpenLineage event with:
- Event metadata (eventTime, eventType, producer)
- Job information (namespace, name, facets)
- Run information (runId, facets)
- Dataset lineage (inputs, outputs)
- dbt-specific facets (dbt_version, processing_engine, etc.)

### Important dbt Integration Notes

**⚠️ Please review the [OpenLineage dbt documentation](https://openlineage.io/docs/integrations/dbt) before running tests.**

Key considerations:
- The `dbt-ol` wrapper has specific configuration requirements
- Event emission timing depends on dbt command type (`run`, `test`, `build`)
- Some dbt facets require specific dbt versions
- File transport configuration affects event file location and format

## What Gets Tested

### Atomic Tests (5 tests)
- **Environment Validation**: dbt and duckdb availability
- **Data Pipeline**: Synthetic CSV data loading and model execution
- **Event Generation**: OpenLineage event capture via file transport
- **Event Structure**: Basic event validity and format compliance

### Framework Tests (5 tests)  
- **Schema Facet Validation**: Schema structure and field compliance
- **SQL Facet Validation**: SQL query capture and dialect specification
- **Lineage Structure Validation**: Event structure and required fields
- **Column Lineage Validation**: Column-level lineage relationship accuracy
- **dbt Job Naming Validation**: dbt-specific naming convention compliance

## Validation Standards

Tests validate against OpenLineage specification requirements:
- Event structure compliance (eventTime, eventType, job, run, producer)
- Required facets presence and structure
- Schema validation for dataset facets
- Lineage relationship accuracy and completeness
- dbt-specific integration patterns

## Spec Compliance Analysis

### Primary Specification Under Test
**OpenLineage Specification 2-0-2** (Latest)
- Implementation: dbt-openlineage 1.37.0
- Core event structure: Fully compliant with 2-0-2 schema
- Main schema URL: `https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent`

### Mixed Facet Versioning (Important Finding)
⚠️ **The implementation uses mixed facet spec versions**:
- **Core event**: 2-0-2 (latest)
- **Job facets**: 2-0-3 (newer than main spec)
- **Run facets**: 1-1-1 (older spec versions)  
- **Dataset facets**: 1-0-1 (older spec versions)

This appears to be intentional for backward/forward compatibility but requires further investigation.

### What We Validate
✅ **Core OpenLineage 2-0-2 compliance**: Event structure, required fields, data types  
✅ **dbt-specific features**: Test events, model events, column lineage, data quality facets  
✅ **Lineage accuracy**: Input/output relationships, parent/child job relationships  
✅ **Event completeness**: All expected events generated for dbt operations  

### What Requires Further Analysis  
🔍 **Mixed facet versioning**: Whether this is spec-compliant or requires separate validation  
🔍 **Cross-version compatibility**: How different facet spec versions interact  
🔍 **Facet-specific validation**: Each facet type against its declared spec version  

See `SPEC_COMPLIANCE_ANALYSIS.md` for detailed analysis of spec version usage.

## Test Structure

```
producer/dbt/
├── run_dbt_tests.sh           # Main test execution script
├── test_runner/               # Python test framework
│   ├── cli.py                # Command-line interface
│   ├── openlineage_test_runner.py  # Atomic test runner
│   └── validation_runner.py   # Event validation logic
├── scenarios/                 # Test scenarios
│   └── csv_to_duckdb_local/   
│       ├── config.json        # Scenario configuration
│       ├── events/            # Expected event templates
│       └── test/              # Scenario-specific tests
├── events/                    # 📁 OpenLineage event output directory
│   └── openlineage_events.jsonl  # Generated events (JSONL format)
├── runner/                    # dbt project for testing
│   ├── dbt_project.yml        # dbt configuration
│   ├── openlineage.yml        # 🔧 OpenLineage transport configuration
│   ├── models/                # dbt models
│   ├── seeds/                 # Sample data
│   └── profiles.yml           # Database connections
└── future/                    # Future enhancement designs
    └── run_multi_spec_tests.sh   # Multi-spec testing prototypes
```

## Internal Test Framework

The test framework consists of:

### CLI Interface (`test_runner/cli.py`)
- Command-line interface for running tests
- Supports both atomic tests and event validation
- Provides detailed output and error reporting

### Atomic Test Runner (`test_runner/openlineage_test_runner.py`)
- Individual validation tests for dbt project components
- Database connectivity validation
- dbt project structure validation
- OpenLineage configuration validation

### Event Validation Runner (`test_runner/validation_runner.py`)
- Framework integration for event validation
- Schema compliance checking
- Event structure validation

## Event Generation Process

### How Events Are Generated

1. **dbt-ol Wrapper Execution**: The test uses `dbt-ol` instead of `dbt` directly
2. **OpenLineage Integration**: Events are emitted during dbt model runs and tests
3. **File Transport**: Events are written to `events/openlineage_events.jsonl`
4. **Event Types**: Both `START` and `COMPLETE` events are generated for each dbt operation

### Event File Format

The generated `events/openlineage_events.jsonl` contains one JSON event per line:

```json
{
  "eventTime": "2025-09-21T08:11:06.838051+00:00",
  "eventType": "START",
  "producer": "https://github.com/OpenLineage/OpenLineage/tree/1.37.0/integration/dbt",
  "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
  "job": { "namespace": "dbt", "name": "..." },
  "run": { "runId": "...", "facets": { "dbt_version": {...}, "processing_engine": {...} } },
  "inputs": [...],
  "outputs": [...]
}
```

### dbt-Specific Event Features

- **dbt Test Events**: Include `dataQualityAssertions` facets with test results
- **dbt Model Events**: Include schema, SQL, and column lineage facets
- **dbt Version Tracking**: Events include dbt and openlineage-dbt version information
- **Parent/Child Relationships**: Test events reference their parent dbt run

## Important Notes

**Test Purpose**: This is a compatibility validation test with synthetic data, not a production use case. The purpose is to validate that dbt properly integrates with OpenLineage and generates compliant events.

**Data**: Uses toy/synthetic data specifically designed for testing OpenLineage compliance, not representative of real-world scenarios.

## Community Contribution

This compatibility test framework is designed for contribution to the OpenLineage community testing infrastructure. It provides:

- **Validation Framework**: Reusable test patterns for dbt OpenLineage integration
- **Reference Implementation**: Example of comprehensive compatibility testing
- **Community Standards**: Alignment with OpenLineage compatibility test conventions

**Scope**: Compatibility validation using synthetic test data, not production use case demonstration.

## Future Enhancements

See the `future/` directory for design documents and prototypes of upcoming features:
- **Multi-spec testing**: Test same implementation against multiple OpenLineage spec versions
- **Multi-implementation testing**: Test different dbt-openlineage versions

## Maintainers

**Maintainer**: BearingNode Team  
**Contact**: contact@bearingnode.com  
**Website**: https://www.bearingnode.com

See `maintainers.json` for current maintainer contact information.