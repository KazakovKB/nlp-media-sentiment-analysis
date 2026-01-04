FROM python:3.13.5-slim

WORKDIR /src

COPY src/app/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY alembic.ini .
COPY migrations ./migrations
COPY scripts/import_lenta.py ./scripts/import_lenta.py
COPY models ./models

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8080"]