import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp, date_format
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType
)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-cluster-kafka-bootstrap:9092")
KAFKA_TOPIC     = os.getenv("KAFKA_TOPIC", "raw-events")
MINIO_ENDPOINT  = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS    = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET    = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET    = os.getenv("MINIO_BUCKET", "events")
CHECKPOINT_PATH = os.getenv("CHECKPOINT_PATH", "s3a://events/checkpoints/kafka-to-minio")

schema = StructType([
    StructField("node_id",    StringType(),  True),
    StructField("timestamp",  StringType(),  True),
    StructField("event_type", StringType(),  True),
    StructField("user_id",    IntegerType(), True),
    StructField("value",      DoubleType(),  True),
])

def main():
    spark = (
        SparkSession.builder
        .appName("KafkaToMinIO")
        .config("spark.hadoop.fs.s3a.endpoint",               MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key",             MINIO_ACCESS)
        .config("spark.hadoop.fs.s3a.secret.key",             MINIO_SECRET)
        .config("spark.hadoop.fs.s3a.path.style.access",      "true")
        .config("spark.hadoop.fs.s3a.impl",
                "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    raw_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )

    parsed_df = (
        raw_df
        .select(from_json(col("value").cast("string"), schema).alias("data"))
        .select("data.*")
        .withColumn("event_ts", to_timestamp(col("timestamp")))
        .withColumn("date",     date_format(col("event_ts"), "yyyy-MM-dd"))
        .withColumn("hour",     date_format(col("event_ts"), "HH"))
    )

    query = (
        parsed_df.writeStream
        .format("parquet")
        .option("path",             f"s3a://{MINIO_BUCKET}/raw/")
        .option("checkpointLocation", CHECKPOINT_PATH)
        .partitionBy("date", "hour", "node_id")
        .outputMode("append")
        .trigger(processingTime="30 seconds")
        .start()
    )

    query.awaitTermination()

if __name__ == "__main__":
    main()
