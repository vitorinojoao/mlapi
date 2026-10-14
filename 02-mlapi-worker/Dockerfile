FROM python:3.12-slim

## Assign Python environmental variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

## Create unprivileged user 'worker'
RUN groupadd --system --gid 10002 worker \
    && useradd --system --uid 10002 --gid worker --home-dir /nonexistent --no-create-home worker

## Copy necessary files and change owner
WORKDIR /worker

COPY --chown=10002:10002 requirements.txt ./requirements.txt
COPY --chown=10002:10002 worker.py ./worker.py
COPY --chown=10002:10002 resources ./source
COPY --chown=10002:10002 resources ./resources

## Install package dependencies
RUN pip install --no-cache-dir -r requirements.txt

## Execute worker command as unprivileged user
USER 10002:10002

CMD ["python", "worker.py"]
