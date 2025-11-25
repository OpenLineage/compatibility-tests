import time

from pyspark.sql import SparkSession

spark = SparkSession.builder.master("local").appName("simple test").enableHiveSupport().getOrCreate()

spark.sql("DROP TABLE IF EXISTS t1;")
spark.sql("DROP TABLE IF EXISTS t2;")

spark.sql("CREATE TABLE IF NOT EXISTS t1 (a INT, b STRING);")
spark.sql("INSERT INTO t1 VALUES (1,2),(3,4);")
spark.sql("CREATE TABLE IF NOT EXISTS t2 AS SELECT * FROM t1;")

time.sleep(3)

spark.sql("SELECT * FROM t2;").show()