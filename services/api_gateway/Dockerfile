FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any are needed for asyncpg etc.
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# We mount the code via volumes in docker-compose.yml so we don't need to copy main.py here

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
