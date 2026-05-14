FROM python:3.11-slim

WORKDIR /app

# Copy shared libs first (layer cache)
COPY services/shared /app/shared

# Copy service files
COPY services/intent_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY services/intent_agent/ .

ENV PYTHONPATH=/app:/app/shared

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
