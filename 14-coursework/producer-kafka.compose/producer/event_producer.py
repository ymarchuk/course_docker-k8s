"""
Мінімальний генератор подій для Kafka з двох нод.
Запускати окремо на кожній ноді з різним NODE_ID.

Використання:
  NODE_ID=node-1 python event_producer.py
  NODE_ID=node-2 python event_producer.py
"""

import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

from kafka import KafkaProducer

# ─── Конфігурація ────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka-dev-kafka-bootstrap.strimzi.svc.cluster.local:9092",
)
KAFKA_TOPIC   = os.getenv("KAFKA_TOPIC", "raw-events")
NODE_ID       = os.getenv("NODE_ID", "node-1")        # node-1 або node-2
SEND_INTERVAL = float(os.getenv("SEND_INTERVAL", "1.0"))  # секунди між подіями

# ─── Типи подій ──────────────────────────────────────────────────────────────

EVENT_TYPES = ["click", "view", "purchase", "login", "logout", "error"]

SENSOR_METRICS = {
    "temperature": (15.0, 40.0),
    "humidity":    (30.0, 90.0),
    "pressure":    (950.0, 1050.0),
    "cpu_usage":   (0.0, 100.0),
    "memory_mb":   (100.0, 8192.0),
}

# ─── Ініціалізація Producer ───────────────────────────────────────────────────

def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        # Надійність
        acks="all",
        retries=3,
        retry_backoff_ms=500,
        # Продуктивність
        batch_size=16384,
        linger_ms=10,
        compression_type="gzip",
    )

# ─── Генерація події ──────────────────────────────────────────────────────────

def generate_event(node_id: str) -> dict:
    """Генерує одну подію від конкретної ноди."""
    event_type = random.choice(EVENT_TYPES)
    metrics = {
        metric: round(random.uniform(low, high), 2)
        for metric, (low, high) in SENSOR_METRICS.items()
    }

    return {
        "event_id":   str(uuid.uuid4()),
        "node_id":    node_id,
        "event_type": event_type,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "payload": {
            "user_id":  f"user_{random.randint(1000, 9999)}",
            "session":  str(uuid.uuid4())[:8],
            "metrics":  metrics,
            "tags":     [node_id, event_type, "v1"],
        },
    }

# ─── Callbacks ────────────────────────────────────────────────────────────────

def on_send_success(record_metadata, event_id: str):
    print(
        f"[OK] event_id={event_id} "
        f"topic={record_metadata.topic} "
        f"partition={record_metadata.partition} "
        f"offset={record_metadata.offset}"
    )

def on_send_error(exc, event_id: str):
    print(f"[ERROR] event_id={event_id} error={exc}")

# ─── Головний цикл ────────────────────────────────────────────────────────────

def main():
    print(f"Starting producer: node={NODE_ID}, topic={KAFKA_TOPIC}, "
          f"bootstrap={KAFKA_BOOTSTRAP_SERVERS}")

    producer = create_producer()

    sent_count = 0
    try:
        while True:
            event    = generate_event(NODE_ID)
            event_id = event["event_id"]

            # Ключ партиціювання — по node_id (події однієї ноди йдуть в одну партицію)
            (
                producer
                .send(KAFKA_TOPIC, key=NODE_ID, value=event)
                .add_callback(on_send_success, event_id)
                .add_errback(on_send_error, event_id)
            )

            sent_count += 1
            if sent_count % 10 == 0:
                producer.flush()
                print(f"[FLUSH] node={NODE_ID}, total_sent={sent_count}")

            time.sleep(SEND_INTERVAL)

    except KeyboardInterrupt:
        print(f"\nStopping producer. Total sent: {sent_count}")
    finally:
        producer.flush()
        producer.close()
        print("Producer closed.")

if __name__ == "__main__":
    main()
