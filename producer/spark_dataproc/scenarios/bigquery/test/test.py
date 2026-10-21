#!/usr/bin/env python

import sys

from pyspark.sql import SparkSession

spark = SparkSession.builder.appName('Writing to BigQuery').getOrCreate()

# Get the scenario suffix from spark config to avoid concurrent write conflicts
scenario_suffix = spark.conf.get("spark.scenario.suffix", "default")
table_name = f"wordcount_output_{scenario_suffix.replace('-', '_').replace('.', '_')}"

words = spark.read.format('bigquery') \
  .option('table', 'bigquery-public-data:samples.shakespeare') \
  .load()
words.createOrReplaceTempView('words')

# Perform word count.
word_count = spark.sql(
    'SELECT word, SUM(word_count) AS word_count FROM words GROUP BY word')

word_count.write.format('bigquery') \
  .option('table', f'e2e_dataset.{table_name}') \
  .option("temporaryGcsBucket", "open-lineage-e2e") \
  .mode('overwrite') \
  .save()

# Let the OpenLineage listener handle the write's end event while the SparkContext
# is still alive. Otherwise the BigQuery lineage extension can fail on a stopped
# context and the COMPLETE event is emitted without outputs.
spark.sparkContext._jsc.sc().listenerBus().waitUntilEmpty(60000)
spark.stop()
