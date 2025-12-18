import os
import json
from typing import Any
from faststream.rabbit import RabbitBroker

RABBIT_URL = os.getenv("RABBIT_URL")
QUEUE_NAME = os.getenv("QUEUE_NAME")

broker = RabbitBroker(RABBIT_URL)

async def start_broker() -> None:
    await broker.start()

async def stop_broker() -> None:
    await broker.stop()

async def enqueue_analysis_job(payload: dict[str, Any]) -> None:
    await broker.publish(json.dumps(payload), queue=QUEUE_NAME)