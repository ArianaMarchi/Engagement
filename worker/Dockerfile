FROM python:3.12-slim

RUN apt-get update && apt-get install -y cron libpq-dev gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /engagement

COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/worker.py .
COPY worker/crontab /etc/cron.d/worker-cron

RUN chmod 0644 /etc/cron.d/worker-cron \
    && crontab /etc/cron.d/worker-cron \
    && touch /var/log/cron.log

CMD ["sh", "-c", "cron && tail -f /var/log/cron.log"]