# dbt Producer Compatibility Tests

## Description

This test validates dbt's OpenLineage integration compliance using a controlled testing environment. It uses synthetic toy data to test dbt's ability to generate compliant OpenLineage events, focusing on validation rather than representing production use cases.

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

### PIE Framework Validation Tests  
```bash
cd test_runner
python cli.py validate-events
```

### Complete Test Suite
```bash
./run_dbt_tests.sh --openlineage-directory /path/to/openlineage/specs
```

## What Gets Tested

### Atomic Tests (5 tests)
- **Environment Validation**: dbt and duckdb availability
- **Data Pipeline**: Synthetic CSV data loading and model execution
- **Event Generation**: OpenLineage event capture via file transport
- **Event Structure**: Basic event validity and format compliance

### PIE Framework Tests (5 tests)  
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

## Community Contribution

This compatibility test framework is designed for contribution to the OpenLineage community testing infrastructure. It provides:

- **Validation Framework**: Reusable test patterns for dbt OpenLineage integration
- **Reference Implementation**: Example of comprehensive compatibility testing
- **Community Standards**: Alignment with OpenLineage compatibility test conventions

**Scope**: Compatibility validation using synthetic test data, not production use case demonstration.

**Maintainer**: BearingNode Team  
**Contact**: contact@bearingnode.com  
**Website**: https://www.bearingnode.com