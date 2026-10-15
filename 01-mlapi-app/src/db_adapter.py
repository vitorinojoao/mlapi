import json, os, time
from pathlib import Path
import psycopg
from psycopg.rows import dict_row


def secret(name, required=True):
    path = os.getenv(name + "_FILE")
    if path:
        try:
            value = Path(path).read_text().strip()
        except OSError:
            if required: raise
            return ""
    else:
        value = os.getenv(name, "").strip()
    if required and not value:
        raise RuntimeError(f"Missing required secret/config: {name}")
    return value


def connect(dbname, user, password, *, autocommit=False):
    return psycopg.connect(
        host=os.getenv("DB_HOST", "db"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=dbname, user=user, password=password,
        connect_timeout=5, application_name=os.getenv("APP_NAME", "task-platform"),
        autocommit=autocommit, row_factory=dict_row,
    )


def db_credentials(prefix):
    return secret(prefix + "_DB_USER"), secret(prefix + "_DB_PASSWORD")

def retry_init(fn, attempts=40):
    last = None
    for _ in range(attempts):
        try:
            fn(); return
        except Exception as exc:
            last = exc; time.sleep(2)
    raise RuntimeError("Database initialization timed out") from last

