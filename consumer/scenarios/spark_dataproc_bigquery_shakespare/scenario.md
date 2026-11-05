# Description
Events of a Spark job on Dataproc (`shakespeare_on_spark`, OpenLineage 1.23.0) that reads a BigQuery table and writes the
result to a local file: the application's START/COMPLETE events and the START/RUNNING/COMPLETE events of its
`adaptive_spark_plan` jobs.

# Entities
input entity is bigquery table

`bigquery-public-data.samples.shakespeare`

output entity is a file

`file:///tmp/outputs/<timestamp>`

# Facets
Run facets:

- gcp_dataproc_spark
- parent
- processing_engine
- spark_applicationDetails
- spark_jobDetails
- spark_properties

Job facets:

- gcp_lineage
- jobType

Output dataset facets:

- columnLineage
- dataSource
- schema
