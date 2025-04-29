from pyspark.sql import SparkSession

spark = (
        SparkSession.builder
        .appName("BigQuery to Delta on GCS")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .getOrCreate()
    )

words = spark.read.format('bigquery') \
  .option('table', 'bigquery-public-data:samples.shakespeare') \
  .load()
words.createOrReplaceTempView('words')

# Perform word count.
word_count = spark.sql(
    'SELECT word, SUM(word_count) AS word_count FROM words GROUP BY word')

spark.sql("""CREATE TABLE IF NOT EXISTS e2e_delta_table (
    word string,
    word_count long)
USING delta
LOCATION 'gs://open-lineage-e2e/data/bigquery_to_delta/e2e_delta_table'""")


# Write as Delta format to GCS
word_count.writeTo("e2e_delta_table").append()