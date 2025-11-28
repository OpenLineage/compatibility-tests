from pyspark.sql import SparkSession

spark = (
        SparkSession.builder
        .appName("BigQuery to Delta on GCS")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .getOrCreate()
    )

# Get the scenario suffix from spark config to avoid concurrent write conflicts
scenario_suffix = spark.conf.get("spark.scenario.suffix", "default")
table_suffix = scenario_suffix.replace('-', '_').replace('.', '_')
table_name = f"e2e_delta_table_{table_suffix}"
table_location = f"gs://open-lineage-e2e/data/bigquery_to_delta/{table_name}"

words = spark.read.format('bigquery') \
  .option('table', 'bigquery-public-data:samples.shakespeare') \
  .load()
words.createOrReplaceTempView('words')

# Perform word count.
word_count = spark.sql(
    'SELECT word, SUM(word_count) AS word_count FROM words GROUP BY word')

spark.sql(f"""CREATE TABLE IF NOT EXISTS {table_name} (
    word string,
    word_count long)
USING delta
LOCATION '{table_location}'""")


# Write as Delta format to GCS
word_count.writeTo(table_name).append()
