# Description

The scenario involves a Spark job that first writes a generated DataFrame to a Bigtable table, then queries the same table, and finally writes the results to another Bigtable table

# Entities

input entity is Bigtable table

`input_table`

output entity Bigtable table

`output_table`

# Facets

Facets present in the events:

- ColumnLineageDatasetFacet
- DatasourceDatasetFacet
- JobTypeJobFacet
- LifecycleStateChangeDatasetFacet
- ParentRunFacet
- SchemaDatasetFacet
