from pyspark.sql import SparkSession

# Initialize SparkSession
spark = SparkSession.builder \
    .appName("Spark CloudSQL example") \
    .getOrCreate()

db_user = spark.sparkContext.getConf().get("spark.driver.POSTGRESQL_USER")
db_password = spark.sparkContext.getConf().get("spark.driver.POSTGRESQL_PASSWORD")
jdbc_url = f'jdbc:postgresql://localhost:3307/e2etest'

jdbc_query = """
    SELECT js1.k, CONCAT(js1.j1, js2.j2) AS j
    FROM jdbc_source1 js1
    JOIN jdbc_source2 js2
    ON js1.k = js2.k
"""

df1 = spark.read \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("query", jdbc_query) \
    .option("user", db_user) \
    .option("password", db_password) \
    .option("driver", "org.postgresql.Driver") \
    .load()

df1.createOrReplaceTempView("jdbc_result")

query = "SELECT j AS value FROM jdbc_result"

result_df = spark.sql(query)

result_df.write \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("dbtable", "test") \
    .option("user", db_user) \
    .option("password", db_password) \
    .option("driver", "org.postgresql.Driver") \
    .mode("append") \
    .save()
