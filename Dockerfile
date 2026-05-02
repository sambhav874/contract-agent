FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["celery", "-A", "app.tasks.celery_tasks", "worker", "--loglevel=info", "--concurrency=4"]
