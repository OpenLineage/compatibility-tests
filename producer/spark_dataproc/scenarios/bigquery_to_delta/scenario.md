# Description

The scenario involves a Spark job that first reads data from Bigquery table, then queries the same table, and finally writes the results to Delta table

# Entities

input entity is Bigquery table table

`input_table`

output entity is Delta table

`output_table`

# Facets

Facets present in the events:

- ColumnLineageDatasetFacet
- DatasourceDatasetFacet
- JobTypeJobFacet
- LifecycleStateChangeDatasetFacet
- ParentRunFacet
- SQLJobFacet
- SchemaDatasetFacet