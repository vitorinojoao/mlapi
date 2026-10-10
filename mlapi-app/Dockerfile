FROM python:3.12-slim

ARG ARG_APP_PORT \
    ARG_APP_WORKERS \
    ARG_APP_TIMEOUT \
    ARG_APP_GRACEFUL

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1


RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /nonexistent --no-create-home app

WORKDIR /app

COPY --chown=10001:10001 requirements.txt ./requirements.txt
COPY --chown=10001:10001 app.py ./app.py

RUN pip install --no-cache-dir -r requirements.txt

USER 10001:10001

CMD ["sh", "-c", "exec gunicorn \
    --bind 0.0.0.0:${ARG_APP_PORT} \
    --workers ${ARG_APP_WORKERS} \
    --worker-class sync \
    --timeout ${ARG_APP_TIMEOUT} \
    --graceful-timeout ${ARG_APP_GRACEFUL} \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    app:app"]
