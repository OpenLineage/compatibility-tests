# Description

The scenario involves a Spark job that first reads data from BigQuery table, then queries the same table, and finally writes the results to Iceberg table

# Entities

input entity is BigQuery table

`input_table`

output entity is Iceberg table

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
- CatalogDatasetFacet