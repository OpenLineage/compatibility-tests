import time

from pyspark.sql import SparkSession

spark = SparkSession.builder.master("local").appName("hive insert test").enableHiveSupport().getOrCreate()

spark.sql("DROP TABLE IF EXISTS t1;")
spark.sql("DROP TABLE IF EXISTS t2;")

spark.sql("CREATE TABLE IF NOT EXISTS t1 (a INT, b STRING);")
spark.sql("INSERT INTO t1 VALUES (1,2),(3,4);")
# CREATE + INSERT instead of CTAS: CTAS runs a nested insert whose COMPLETE event often has the same
# millisecond eventTime as the CTAS COMPLETE, and GcsTransport drops one of them (see hive scenario)
spark.sql("CREATE TABLE IF NOT EXISTS t2 (a INT, b STRING);")
spark.sql("INSERT INTO t2 SELECT * FROM t1;")

time.sleep(3)

spark.sql("SELECT * FROM t2;").show()
