from pyspark.sql import SparkSession

# Create Spark session
spark = SparkSession.builder \
    .appName("Spark Spanner Example") \
    .getOrCreate()

# Spanner configuration
project_id = "gcp-open-lineage-testing"
instance_id = "spaner-openlineage-testing-instance"
database_id = "test-database"

# Define Spanner table names
table_name = "test_table"

if __name__ == "__main__":
    df = spark.read.format('cloud-spanner') \
        .option("projectId", project_id) \
        .option("instanceId", instance_id) \
        .option("databaseId", database_id) \
        .option("table", table_name).load()
    aggregated_df = df.groupBy("Name").max("Value").withColumnRenamed("sum(Value)", "totalValue")
    aggregated_df.show()

