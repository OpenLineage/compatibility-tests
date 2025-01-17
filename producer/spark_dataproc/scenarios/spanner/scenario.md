# Description

Scenario contains a spark job that reads from a bigquery table, filters the data, aggregates it and writes to a bigquery table
`e2e_dataset.wordcount_output`
# Entities

input entity is bigquery table

`bigquery-public-data.samples.shakespeare`

output entity local csv file

`e2e_dataset.wordcount_output`

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
