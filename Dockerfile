FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest.py .
COPY run_loop.py .

CMD ["python", "-u", "run_loop.py"]