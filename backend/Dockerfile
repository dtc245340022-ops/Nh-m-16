FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/conference.db

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app *.py ./
COPY --chown=app:app docker-entrypoint.sh ./
RUN mkdir -p /data && chown app:app /data

USER app
EXPOSE 8001

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
