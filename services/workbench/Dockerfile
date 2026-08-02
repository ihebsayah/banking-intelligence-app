FROM python:3.11-slim

WORKDIR /app/services

RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "workbench.main:app", "--host", "0.0.0.0", "--port", "8014"]
