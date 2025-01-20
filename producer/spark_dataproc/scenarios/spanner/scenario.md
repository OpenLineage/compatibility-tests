# Description

Scenario contains a spark job that reads from a spanner table, aggregates the data and writes to a csv file (writes not supported for spark spanner connector)

# Entities

input entity is bigquery table

`test-database/test_table`

output entity local csv file

`/user/root/output`

# Facets

Facets present in the events:

- ColumnLineageDatasetFacet
- DatasourceDatasetFacet
- JobTypeJobFacet
- LifecycleStateChangeDatasetFacet
- ParentRunFacet
- SQLJobFacet
- SchemaDatasetFacet
- SymlinksDatasetFacet
