#!/usr/bin/env python

import sys

from pyspark.sql import SparkSession

spark = SparkSession.builder.appName('Writing to BigQuery').getOrCreate()

# Get the scenario suffix from spark config to avoid concurrent write conflicts
scenario_suffix = spark.conf.get("spark.scenario.suffix", "default")
dataset_name = f"e2e_dataset_{scenario_suffix.replace('-', '_').replace('.', '_')}"

words = spark.read.format('bigquery') \
  .option('table', 'bigquery-public-data:samples.shakespeare') \
  .load()
words.createOrReplaceTempView('words')

# Perform word count.
word_count = spark.sql(
    'SELECT word, SUM(word_count) AS word_count FROM words GROUP BY word')

word_count.write.format('bigquery') \
  .option('table', f'{dataset_name}.wordcount_output') \
  .option("temporaryGcsBucket", "open-lineage-e2e") \
  .mode('overwrite') \
  .save()
