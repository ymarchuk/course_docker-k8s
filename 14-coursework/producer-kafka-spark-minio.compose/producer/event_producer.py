"""
Event producer — генерує події та відправляє в Kafka.
NODE_ID визначає від якої ноди йдуть події.
"""

import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

# ─── Конфігурація ─────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC             = os.getenv("KAFKA_TOPIC",             "raw-events")
NODE_ID                 = os.getenv("NODE_ID",                 "node-1")
SEND_INTERVAL           = float(os.getenv("SEND_INTERVAL",     "1.0"))

EVENT_TYPES    = ["click", "view", "purchase", "login", "logout", "error"]
SENSOR_METRICS = {
    "temperature": (15.0,  40.0),
    "humidity":    (30.0,  90.0),
    "cpu_usage":   ( 0.0, 100.0),
    "memory_mb":   (100.0, 8192.0),
}

# ─── Producer з retry при старті ─────────────────────────────────
def create_producer(retries: int = 10, delay: int = 5) -> KafkaProducer:
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8"),
                acks="all",
                retries=3,
                retry_backoff_ms=500,
                compression_type="gzip",
            )
            print(f"[{NODE_ID}] ✅ Connected to Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
            return producer
        except NoBrokersAvailable:
            print(f"[{NODE_ID}] ⏳ Kafka not ready, attempt {attempt}/{retries}. "
                  f"Retry in {delay}s...")
            time.sleep(delay)
    raise RuntimeError(f"[{NODE_ID}] ❌ Cannot connect to Kafka after {retries} attempts")

# ─── Генерація події ─────────────────────────────────────────────
def generate_event() -> dict:
    return {
        "event_id":   str(uuid.uuid4()),
        "node_id":    NODE_ID,
        "event_type": random.choice(EVENT_TYPES),
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "payload": {
            "user_id": f"user_{random.randint(1000, 9999)}",
            "session": str(uuid.uuid4())[:8],
            "metrics": {
                metric: round(random.uniform(low, high), 2)
                for metric, (low, high) in SENSOR_METRICS.items()
            },
        },
    }

# ─── Callbacks ───────────────────────────────────────────────────
def on_success(meta, event_id):
    print(f"[{NODE_ID}] ✅ sent event_id={event_id} "
          f"partition={meta.partition} offset={meta.offset}")

def on_error(exc, event_id):
    print(f"[{NODE_ID}] ❌ error event_id={event_id}: {exc}")

# ─── Main ────────────────────────────────────────────────────────
def main():
    print(f"[{NODE_ID}] Starting producer → topic={KAFKA_TOPIC} "
          f"interval={SEND_INTERVAL}s")

    producer = create_producer()
    count    = 0

    try:
        while True:
            event    = generate_event()
            event_id = event["event_id"]

            (
                producer
                .send(KAFKA_TOPIC, key=NODE_ID, value=event)
                .add_callback(on_success, event_id)
                .add_errback(on_error, event_id)
            )

            count += 1
            if count % 20 == 0:
                producer.flush()
                print(f"[{NODE_ID}] 📦 Flushed. Total sent: {count}")

            time.sleep(SEND_INTERVAL)

    except KeyboardInterrupt:
        print(f"[{NODE_ID}] Stopping. Total sent: {count}")
    finally:
        producer.flush()
        producer.close()

if __name__ == "__main__":
    main()
