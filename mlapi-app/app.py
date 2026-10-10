import os
from urllib.parse import urlparse

import psycopg
import requests
from flask import Flask, jsonify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

APP_EXTERNAL_URL_1 = os.environ["APP_EXTERNAL_URL_1"].rstrip("/")
parsed = urlparse(APP_EXTERNAL_URL_1)

if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
    raise RuntimeError("External API must be a valid HTTPS URL")

def secret(name):
    path = os.environ[name + "_FILE"]
    with open(path, encoding="utf-8") as f:
        value = f.read().strip()
    if not value:
        raise RuntimeError(f"Empty secret: {name}")
    return value

def db_config(prefix):
    return {
        "port": os.environ["ARG_DB_PORT"],
        "host": os.environ["ARG_DB_HOST"],
        "dbname": os.environ[prefix + "_DB_NAME"],
        "user": os.environ[prefix + "_DB_USER"],
        "password": secret(prefix + "_DB_PASSWORD"),
        "connect_timeout": 3,
        "sslmode": "disable",
        "application_name": "secure-flask-api",
    }

DBS = {
    "auth": db_config("AUTH"),
    "config": db_config("CONFIG"),
    "data": db_config("DATA"),
}

def connect_db(name):
    # Only use fixed keys defined above; never derive database names from input.
    return psycopg.connect(**DBS[name])

# Never trust arbitrary client-supplied URLs. Use a fixed configured origin.
http = requests.Session()
http.trust_env = False
http.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=2,
            connect=2,
            read=0,
            status=0,
            backoff_factor=0.2,
            allowed_methods=frozenset(["GET"]),
        )
    ),
)

@app.get("/health")
def health():
    # Liveness check; does not depend on PostgreSQL.
    return jsonify(status="ok"), 200

@app.get("/ready")
def ready():
    try:
        with connect_db("data") as conn:
            conn.execute("SELECT 1")
        return jsonify(status="ready"), 200
    except psycopg.Error:
        app.logger.exception("Database readiness check failed")
        return jsonify(error="not ready"), 503

@app.get("/api/example")
def example():
    try:
        with connect_db("data") as conn:
            row = conn.execute("SELECT current_database()").fetchone()
        return jsonify(database=row[0]), 200
    except psycopg.Error:
        app.logger.exception("Database operation failed")
        return jsonify(error="database unavailable"), 503

def fetch_external_status():
    response = http.get(
        APP_EXTERNAL_URL_1 + "/status",
        timeout=(3, 10),
        allow_redirects=False,
    )
    response.raise_for_status()
    return response.json()
