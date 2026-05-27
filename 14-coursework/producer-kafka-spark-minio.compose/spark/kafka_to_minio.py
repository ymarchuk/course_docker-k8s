"""
Spark Structured Streaming:
  Kafka (raw-events) → parse JSON → MinIO (Parquet)
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, StringType, StructField,
    StructType, ArrayType,
)

# ─── Конфігурація ─────────────────────────────────────────────────
KAFKA_BOOTSTRAP  = os.getenv("KAFKA_BOOTSTRAP",  "kafka:29092")
KAFKA_TOPIC      = os.getenv("KAFKA_TOPIC",      "raw-events")
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET",     "events")
TRIGGER_INTERVAL = os.getenv("TRIGGER_INTERVAL", "30 seconds")

OUTPUT_PATH     = f"s3a://{MINIO_BUCKET}/data/"
CHECKPOINT_PATH = f"s3a://checkpoints/kafka-to-minio/"

# ─── Схема JSON ───────────────────────────────────────────────────
EVENT_SCHEMA = StructType([
    StructField("event_id",   StringType(), True),
    StructField("node_id",    StringType(), True),
    StructField("event_type", StringType(), True),
    StructField("timestamp",  StringType(), True),
    StructField("payload", StructType([
        StructField("user_id", StringType(), True),
        StructField("session", StringType(), True),
        StructField("metrics", StructType([
            StructField("temperature", DoubleType(), True),
            StructField("humidity",    DoubleType(), True),
            StructField("cpu_usage",   DoubleType(), True),
            StructField("memory_mb",   DoubleType(), True),
        ]), True),
    ]), True),
])

# ─── SparkSession ─────────────────────────────────────────────────
def create_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("KafkaToMinIO")
        .config("spark.hadoop.fs.s3a.endpoint",          MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key",        MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key",        MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl",
                "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

# ─── Трансформація ────────────────────────────────────────────────
def transform(raw_df):
    return (
        raw_df
        .withColumn("json_str", F.col("value").cast(StringType()))
        .withColumn("e",        F.from_json("json_str", EVENT_SCHEMA))
        .select(
            F.col("e.event_id").alias("event_id"),
            F.col("e.node_id").alias("node_id"),
            F.col("e.event_type").alias("event_type"),
            F.to_timestamp("e.timestamp").alias("event_time"),
            F.col("e.payload.user_id").alias("user_id"),
            F.col("e.payload.session").alias("session_id"),
            F.col("e.payload.metrics.temperature").alias("temperature"),
            F.col("e.payload.metrics.humidity").alias("humidity"),
            F.col("e.payload.metrics.cpu_usage").alias("cpu_usage"),
            F.col("e.payload.metrics.memory_mb").alias("memory_mb"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.current_timestamp().alias("processed_at"),
        )
        # Колонки для партиціювання у MinIO
        .withColumn("year",    F.year("event_time"))
        .withColumn("month",   F.month("event_time"))
        .withColumn("day",     F.dayofmonth("event_time"))
        .withColumn("hour",    F.hour("event_time"))
    )

# ─── Запис батчу в MinIO ──────────────────────────────────────────
def write_batch(df, epoch_id: int):
    if df.isEmpty():
        print(f"[epoch={epoch_id}] ⏭️  Empty batch, skip.")
        return
    count = df.count()
    print(f"[epoch={epoch_id}] 💾 Writing {count} records → {OUTPUT_PATH}")
    (
        df.write
        .mode("append")
        .partitionBy("year", "month", "day", "hour", "node_id")
        .parquet(OUTPUT_PATH)
    )
    print(f"[epoch={epoch_id}] ✅ Done.")

# ─── Main ────────────────────────────────────────────────────────
def main():
    print(f"🚀 Spark Streaming starting...")
    print(f"   Kafka:   {KAFKA_BOOTSTRAP} → {KAFKA_TOPIC}")
    print(f"   MinIO:   {MINIO_ENDPOINT}  → {OUTPUT_PATH}")
    print(f"   Trigger: {TRIGGER_INTERVAL}")

    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe",               KAFKA_TOPIC)
        .option("startingOffsets",         "latest")
        .option("failOnDataLoss",          "false")
        .option("maxOffsetsPerTrigger",    "5000")
        .load()
    )

    transformed = transform(raw)

    query = (
        transformed.writeStream
        .outputMode("append")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .foreachBatch(write_batch)
        .option("checkpointLocation", CHECKPOINT_PATH)
        .start()
    )

    print("✅ Streaming query started. Waiting for data...")
    query.awaitTermination()

if __name__ == "__main__":
    main()
