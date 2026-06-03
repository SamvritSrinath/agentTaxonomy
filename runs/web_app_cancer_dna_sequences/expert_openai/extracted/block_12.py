import json
from confluent_kafka import Producer, Consumer
from .config import settings


def kafka_producer():
    return Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})


def publish(topic: str, key: str, value: dict):
    producer = kafka_producer()
    producer.produce(topic, key=key, value=json.dumps(value).encode("utf-8"))
    producer.flush(10)


def kafka_consumer(group_id: str, topics: list[str]):
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe(topics)
    return consumer
