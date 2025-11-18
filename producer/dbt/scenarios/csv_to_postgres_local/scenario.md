# CSV to PostgreSQL Local Scenario

## Overview

This scenario validates dbt's OpenLineage integration compliance using synthetic test data in a controlled CSV → dbt → PostgreSQL pipeline with local file transport.

**Purpose**: Compatibility testing and validation, not production use case demonstration.

## Data Flow

```
Synthetic CSV Files (customers.csv, orders.csv)
    ↓ (dbt seed)
PostgreSQL Raw Tables
    ↓ (dbt models)  
Staging Models (stg_customers, stg_orders)
    ↓ (dbt models)
Analytics Model (customer_analytics)
```

## Test Coverage

The scenario validates the following OpenLineage facets:

- **Schema Facets**: Column definitions and data types
- **SQL Facets**: Actual SQL transformations executed by dbt
- **Lineage**: Dataset-level lineage relationships  
- **Column Lineage**: Field-level transformations and dependencies

## Test Data Logic

Synthetic customer analytics scenario designed for validation testing:
- Import synthetic customer and order data from CSV files
- Clean and standardize data in staging layer  
- Create aggregated customer metrics in analytics layer

**Note**: This uses entirely synthetic data designed to test OpenLineage integration, not representative of production data patterns.

## Technical Details

- **Source**: Synthetic CSV files with test customer and order data
- **Transform**: dbt models with staging and analytics layers
- **Target**: DuckDB database (local file)
- **Transport**: OpenLineage file transport (JSONL events)
- **Validation**: Comprehensive facet compliance testing

## Expected Outputs

- 8 OpenLineage events for dbt job and model executions
- Schema facets describing table structures and column definitions
- SQL facets with actual transformation queries and dialect information
- Column lineage facets showing field-level transformations
- Dataset lineage tracking data flow between models

## Validation Framework

This scenario serves as a test harness for validating:
- dbt OpenLineage integration functionality
- OpenLineage event structure compliance
- Facet generation accuracy and completeness
- Community compatibility testing standards
- Lineage relationships between datasets
- Column lineage for field-level tracking