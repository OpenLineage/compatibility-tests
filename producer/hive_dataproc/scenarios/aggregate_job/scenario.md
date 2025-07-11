# Description
Scenario contains a spark job that executes spark sql queries

DROP TABLE IF EXISTS t1;
DROP TABLE IF EXISTS t2;

CREATE TABLE IF NOT EXISTS t1 (a INT, b STRING);

INSERT INTO t1 VALUES (1,2),(3,4);
CREATE TABLE IF NOT EXISTS t2 AS SELECT * FROM t1;


# Entities

input entity is hive table

`default.t1`

output entity hive table
`default.t2`

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
