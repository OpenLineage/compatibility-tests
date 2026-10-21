# Description
Scenario contains a spark job that executes spark sql queries

DROP TABLE IF EXISTS t1;
DROP TABLE IF EXISTS t2;

CREATE TABLE IF NOT EXISTS t1 (a INT, b STRING);

INSERT INTO t1 VALUES (1,2),(3,4);
CREATE TABLE IF NOT EXISTS t2 (a INT, b STRING);
INSERT INTO t2 SELECT * FROM t1;

It covers the same lineage as the `hive` scenario, without CTAS. CTAS runs a nested insert whose COMPLETE
event often has the same millisecond `eventTime` as the CTAS COMPLETE, and `GcsTransport` names files by
that timestamp, so one of the events is dropped. The `hive` scenario is enabled again once the transport is fixed.

# Entities

input entity is hive table

`hive_insert.t1`

output entity hive table
`hive_insert.t2`

# Facets
Facets present in the events:
- ColumnLineageDatasetFacet
- DatasourceDatasetFacet
- JobTypeJobFacet
- ParentRunFacet
- SQLJobFacet
- SchemaDatasetFacet
- SymlinksDatasetFacet
