FROM python:3.11-slim

WORKDIR /app

COPY services/shared /app/shared
COPY services/schema_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/schema_agent/ .

ENV PYTHONPATH=/app:/app/shared

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
