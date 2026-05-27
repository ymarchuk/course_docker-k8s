import os
import json
import time
import random
import logging
from datetime import datetime
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-cluster-kafka-bootstrap:9092")
TOPIC           = os.getenv("KAFKA_TOPIC", "raw-events")
NODE_ID         = os.getenv("NODE_ID", "node-0")
INTERVAL        = float(os.getenv("PRODUCE_INTERVAL", "1.0"))

def create_producer():
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8"),
                retries=5,
            )
            logger.info("Connected to Kafka: %s", KAFKA_BOOTSTRAP)
            return producer
        except Exception as e:
            logger.warning("Kafka not ready: %s — retrying in 5s", e)
            time.sleep(5)

def generate_event():
    return {
        "node_id":    NODE_ID,
        "timestamp":  datetime.utcnow().isoformat(),
        "event_type": random.choice(["click", "view", "purchase", "logout"]),
        "user_id":    random.randint(1000, 9999),
        "value":      round(random.uniform(0.1, 500.0), 2),
    }

def main():
    producer = create_producer()
    logger.info("Starting event production on node: %s", NODE_ID)
    try:
        while True:
            event = generate_event()
            producer.send(TOPIC, key=NODE_ID, value=event)
            logger.info("Sent: %s", event)
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logger.info("Shutting down producer")
    finally:
        producer.flush()
        producer.close()

if __name__ == "__main__":
    main()
