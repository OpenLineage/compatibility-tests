from pyspark.sql import SparkSession

spark = (
        SparkSession.builder
        .appName("BigLake to Iceberg")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.gcp_iceberg_catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.gcp_iceberg_catalog.catalog-impl", "org.apache.iceberg.gcp.bigquery.BigQueryMetastoreCatalog")
        .config("spark.sql.catalog.gcp_iceberg_catalog.gcp_project", "gcp-open-lineage-testing")
        .config("spark.sql.catalog.gcp_iceberg_catalog.gcp_location", "us-west1")
        .config("spark.sql.catalog.gcp_iceberg_catalog.blms_catalog", "e2e_blms_catalog")
        .config("spark.sql.catalog.gcp_iceberg_catalog.warehouse", f"gs://open-lineage-e2e/data/bigquery_metastore/") 
        .getOrCreate()
    )

spark.catalog.setCurrentCatalog("gcp_iceberg_catalog")

spark.sql(f"CREATE NAMESPACE IF NOT EXISTS e2e_dataset")

# this is an BigLake Iceberg table
words = spark.read.format('bigquery') \
  .option('table', 'e2e_dataset.iceberg_biglake') \
  .load()
  
words.createOrReplaceTempView('words')

word_count = spark.sql(
    'SELECT word, SUM(word_count) AS word_count FROM words GROUP BY word')

word_count.write.format("iceberg").mode("overwrite").saveAsTable("e2e_dataset.e2e_another_table")
