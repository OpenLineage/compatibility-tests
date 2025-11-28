from pyspark.sql import SparkSession

spark = (
        SparkSession.builder
        .appName("BigQuery to Iceberg with BigQueryMetastoreCatalog")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.gcp_iceberg_catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.gcp_iceberg_catalog.catalog-impl", "org.apache.iceberg.gcp.bigquery.BigQueryMetastoreCatalog")
        .config("spark.sql.catalog.gcp_iceberg_catalog.gcp_project", "gcp-open-lineage-testing")
        .config("spark.sql.catalog.gcp_iceberg_catalog.gcp.bigquery.project-id", "gcp-open-lineage-testing")
        .config("spark.sql.catalog.gcp_iceberg_catalog.gcp_location", "us-west1")
        .config("spark.sql.catalog.gcp_iceberg_catalog.blms_catalog", "e2e_blms_catalog")
        .config("spark.sql.catalog.gcp_iceberg_catalog.warehouse", f"gs://open-lineage-e2e/data/bigquery_metastore/") 
        .getOrCreate()
    )

spark.catalog.setCurrentCatalog("gcp_iceberg_catalog")

# Get the scenario suffix from spark config to avoid concurrent write conflicts
scenario_suffix = spark.conf.get("spark.scenario.suffix", "default")
table_name = f"e2e_table_{scenario_suffix.replace('-', '_').replace('.', '_')}"

spark.sql(f"CREATE NAMESPACE IF NOT EXISTS e2e_dataset")

words = spark.read.format('bigquery') \
  .option('table', 'bigquery-public-data:samples.shakespeare') \
  .load()
words.createOrReplaceTempView('words')

# Perform word count.
word_count = spark.sql(
    'SELECT word, SUM(word_count) AS word_count FROM words GROUP BY word')

# Write as Iceberg format to GCS with dynamic dataset name
word_count.write.format("iceberg").mode("overwrite").saveAsTable(f"e2e_dataset.{table_name}")
