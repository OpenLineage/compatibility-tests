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
table_name = "TestTable"
new_table_name = "target_table"

# Sample data
data = [
    (1, "Alice", 10),
    (2, "Bob", 20),
    (3, "Charlie", 30),
    (4, "Alice", 40),
    (5, "Bob", 50),
]
columns = ["Id", "Name", "Value"]


def set_options(read_or_write, table):
    return read_or_write.format('cloud-spanner') \
        .option("projectId", project_id) \
        .option("instanceId", instance_id) \
        .option("databaseId", database_id) \
        .option("table", table)


if __name__ == "__main__":
    # Ensure the right table content
    # df = spark.createDataFrame(data, columns)
    # set_options(df.write, table_name).mode("overwrite").save()

    # trigger operation to get testable OL events

    df = set_options(spark.read, table_name).load()
    df.createOrReplaceTempView('testTable')
    aggregated_df = df.groupBy("Name").sum("Value").withColumnRenamed("max(Timestamp)", "maxTS")
    aggregated_df.show()

