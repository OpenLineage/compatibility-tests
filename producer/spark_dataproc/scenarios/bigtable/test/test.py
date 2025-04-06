from pyspark.sql import SparkSession, Row
import uuid
import json
from google.cloud import bigtable

def generate_test_row(number, start_range):
    return Row(
        stringCol=f"StringCol{number - start_range:03d}",
        stringCol2=f"StringCol2{number - start_range:03d}",
        booleanCol=(number % 2 == 0),
        shortCol=int(number),
        intCol=int(number),
        longCol=int(number),
        floatCol=float(number * 3.14),
        doubleCol=float(number / 3.14)
    )

# def drop_if_exists(instance, table_name):
#     table = instance.table(table_id=table_name)
#     if table.exists():
#         table.delete()

def generate_table_id(test_name):
    return f"cbt-{test_name}-{uuid.uuid4().hex[:20]}"

def create_bigtable_table(table_name, admin_client):
    version_rule = {"maxVersions": 3}
    if not admin_client.exists(table_name):
        create_table_request = {
            "name": table_name,
            "families": {
                "col_family1": version_rule,
                "col_family2": version_rule,
                "col_family3": version_rule,
            },
        }
        admin_client.create_table(create_table_request)
        print(f"Created a CBT table: {table_name}")

def write_dataframe_to_bigtable(dataframe, catalog, project_id, instance_id, create_new_table=False):
    dataframe.write \
        .format("bigtable") \
        .option("catalog", catalog) \
        .option("spark.bigtable.project.id", project_id) \
        .option("spark.bigtable.instance.id", instance_id) \
        .option("spark.bigtable.create.new.table", str(create_new_table).lower()) \
        .save()

def read_dataframe_from_bigtable(spark, catalog, project_id, instance_id):
    return spark.read \
        .format("bigtable") \
        .option("catalog", catalog) \
        .option("spark.bigtable.project.id", project_id) \
        .option("spark.bigtable.instance.id", instance_id) \
        .load()

def create_test_dataframe(spark, num_rows):
    start_range = -(num_rows // 2)
    end_range = (num_rows + 1) // 2
    rows = [generate_test_row(i, start_range) for i in range(start_range, end_range)]
    return spark.createDataFrame(rows)

def delete_bigtable_table(table_name, admin_client):
    if admin_client.exists(table_name):
        admin_client.delete_table(table_name)
        print(f"Deleted CBT table: {table_name}")

spark = SparkSession.builder.appName("BigtableExample").getOrCreate()

suffix = spark.conf.get('spark.scenario.suffix')
test_name = f"test_{suffix}"
input_table = f"input_table_{suffix}"
output_table = f"output_table_{suffix}"

# Assuming admin_client is already set up
# create_bigtable_table(input_table, admin_client)
# create_bigtable_table(output_table, admin_client)

test_df = create_test_dataframe(spark, 10)

raw_basic_catalog = ("""
    {"table":{"name":"%s","tableCoder":"PrimitiveType"},"rowkey":"stringCol",
    "columns":{
        "stringCol":{"cf":"rowkey", "col":"stringCol","type":"string"},
        "stringCol2":{"cf":"col_family1","col":"stringCol2", "type":"string"},
        "booleanCol":{"cf":"col_family1","col":"booleanCol", "type":"boolean"},
        "shortCol":{"cf":"col_family2","col":"shortCol", "type":"short"},
        "intCol":{"cf":"col_family2","col":"intCol", "type":"int"},
        "longCol":{"cf":"col_family2","col":"longCol", "type":"long"},
        "floatCol":{"cf":"col_family3","col":"floatCol", "type":"float"},
        "doubleCol":{"cf":"col_family3","col":"doubleCol", "type":"double"}
        }
    }
""") % input_table

project_id = "gcp-open-lineage-testing"
instance_id = "openlineage-test"

client = bigtable.Client(project=project_id, admin=True)
instance = client.instance(instance_id)

# drop_if_exists(instance, input_table)
# drop_if_exists(instance, output_table)

write_dataframe_to_bigtable(test_df, raw_basic_catalog, project_id, instance_id, True)

read_df = read_dataframe_from_bigtable(spark, raw_basic_catalog, project_id, instance_id)

read_df.createOrReplaceTempView("tempTable")

output_df = spark.sql("SELECT stringCol AS someCol, stringCol2 AS someCol2 FROM tempTable")

output_catalog = ("""
    {"table":{"name":"%s","tableCoder":"PrimitiveType"},"rowkey":"someCol",
    "columns":{
        "someCol":{"cf":"rowkey", "col":"someCol", "type":"string"},
        "someCol2":{"cf":"col_family1","col":"someCol2", "type":"string"}
        }
    }
""") % output_table

write_dataframe_to_bigtable(output_df, output_catalog, project_id, instance_id, True)

spark.stop()

# Cleanup after the run

bt_table1 = instance.table(table_id=input_table)
bt_table2 = instance.table(table_id=output_table)

bt_table1.delete()
bt_table2.delete()