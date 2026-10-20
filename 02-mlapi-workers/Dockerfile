FROM python:3.12-slim

## Assign Python environmental variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

## Create unprivileged user 'workers'
RUN groupadd --system --gid 10002 workers \
    && useradd --system --uid 10002 --gid workers --home-dir /nonexistent --no-create-home workers

## Copy necessary files and change owner
WORKDIR /workers

COPY --chown=10002:10002 requirements.txt ./requirements.txt
COPY --chown=10002:10002 run-workers.py ./run-workers.py
COPY --chown=10002:10002 src ./src
COPY --chown=10002:10002 resources ./resources

## Install package dependencies
RUN pip install --no-cache-dir -r requirements.txt

## Execute 'run-workers' as unprivileged user
USER 10002:10002

CMD ["python", "run-workers.py"]
