import os
import json
import logging
import asyncio

from sqlalchemy.orm import Session
from faststream.rabbit import RabbitBroker
from faststream import FastStream

from src.app.infra.db import SessionLocal
from src.app.infra.uow import SqlAlchemyUoW
from src.app.services.analysis_service import AnalysisService

logging.basicConfig(level=logging.INFO)

RABBIT_URL = os.getenv("RABBIT_URL")
QUEUE_NAME = os.getenv("QUEUE_NAME")

broker = RabbitBroker(RABBIT_URL)
app = FastStream(broker)

@broker.subscriber(QUEUE_NAME)
async def handle(body: str) -> None:
    payload = json.loads(body)
    job_id = int(payload["job_id"])

    db: Session = SessionLocal()
    uow = SqlAlchemyUoW(db)
    svc = AnalysisService(uow)

    try:
        svc.run_job(job_id)
        uow.commit()
        logging.info("analysis job %s DONE", job_id)

    except Exception as exc:
        logging.exception("analysis job %s FAILED: %s", job_id, exc)
        try:
            uow.analysis.set_error(job_id, str(exc))
            uow.commit()
        except Exception:
            uow.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(app.run())