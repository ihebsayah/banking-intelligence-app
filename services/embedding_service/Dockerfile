FROM python:3.11-slim

WORKDIR /app

COPY services/shared /app/shared
COPY services/embedding_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model into the image layer (saves startup time)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY services/embedding_service/ .

ENV PYTHONPATH=/app:/app/shared

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8009"]
