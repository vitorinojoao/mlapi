"""app"""

import os
import logging
import atexit
from pathlib import Path

from flask import Flask, request, jsonify
from flask_security import Security
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

from src.db_auth_adapter import DBAuthAdapter
from src.db_data_adapter import DBDataAdapter
from src.feature_encoder import FeatureEncoder
from src.model_wrapper import ModelWrapper

from src.blueprint_auth import create_blueprint_auth
from src.blueprint_private import create_blueprint_private
from src.blueprint_tasks import create_blueprint_tasks


def create_app():
    logging.warning("create_app")

    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=read_secret_file("FLASK_SECRET_KEY_FILE"),
        SECURITY_PASSWORD_SALT=read_secret_file("SECURITY_PASSWORD_SALT_FILE"),
        SECURITY_PASSWORD_HASH="argon2",
        SECURITY_PASSWORD_LENGTH_MIN=int(
            os.getenv("SECURITY_PASSWORD_LENGTH_MIN", "14")
        ),
        SECURITY_PASSWORD_COMPLEXITY_CHECKER="zxcvbn",
        SECURITY_ZXCVBN_MINIMUM_SCORE=int(
            os.getenv("SECURITY_ZXCVBN_MINIMUM_SCORE", "3")
        ),
        SECURITY_TOKEN_AUTHENTICATION_HEADER=os.getenv(
            "SECURITY_TOKEN_HEADER", "Authentication-Token"
        ),
        SECURITY_TOKEN_MAX_AGE=int(os.getenv("SECURITY_TOKEN_TTL_SECONDS", "900")),
        SECURITY_TOKEN_AUTHENTICATION_ENABLED=True,
        SECURITY_SESSION_AUTHENTICATION_ENABLED=False,
        SECURITY_BASIC_AUTHENTICATION_ENABLED=False,
        SECURITY_REGISTERABLE=False,
        SECURITY_RECOVERABLE=False,
        SECURITY_CHANGEABLE=False,
        SECURITY_CONFIRMABLE=False,
        SECURITY_SEND_REGISTER_EMAIL=False,
        SECURITY_SEND_PASSWORD_CHANGE_EMAIL=False,
        SECURITY_SEND_PASSWORD_RESET_NOTICE_EMAIL=False,
        SECURITY_JSON=True,
        SECURITY_CSRF_PROTECT_MECHANISMS=[],
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_REQUEST_BYTES", "2000000")),
        TRUSTED_HOSTS=[
            x.strip()
            for x in os.getenv(
                "TRUSTED_HOSTS", "api.home.arpa,localhost,127.0.0.1"
            ).split(",")
            if x.strip()
        ],
        RATELIMIT_STORAGE_URI=os.getenv(
            "RATELIMIT_STORAGE_URI", "redis://redis:6379/0"
        ),
        RATELIMIT_STRATEGY=os.getenv("RATE_LIMIT_STRATEGY", "moving-window"),
        RATELIMIT_HEADERS_ENABLED=True,
        RATELIMIT_DEFAULT=os.getenv("RATE_LIMIT_DEFAULT", "120 per minute"),
        RATELIMIT_ENABLED=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
        # ----------
        SECRET_KEY=read_secret_file("FLASK_SECRET_KEY"),
        SECURITY_PASSWORD_SALT=read_secret_file("SECURITY_PASSWORD_SALT"),
        SQLALCHEMY_DATABASE_URI="sqlite:////tmp/flask-security-bootstrap.sqlite",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 300},
        # API-only: no session/basic authentication and no form-oriented features.
        SECURITY_API_ENABLED_METHODS=["token"],
        SECURITY_URL_PREFIX="/auth",
        SECURITY_REGISTERABLE=False,
        SECURITY_CONFIRMABLE=False,
        SECURITY_RECOVERABLE=False,
        SECURITY_CHANGEABLE=False,
        SECURITY_UNIFIED_SIGNIN=False,
        SECURITY_TRACKABLE=True,
        SECURITY_SEND_REGISTER_EMAIL=False,
        SECURITY_PASSWORD_HASH="argon2",
        SECURITY_PASSWORD_LENGTH_MIN=int(
            os.getenv("SECURITY_PASSWORD_LENGTH_MIN", "14")
        ),
        SECURITY_PASSWORD_COMPLEXITY_CHECKER="zxcvbn",
        SECURITY_ZXCVBN_MINIMUM_SCORE=int(
            os.getenv("SECURITY_ZXCVBN_MINIMUM_SCORE", "3")
        ),
        SECURITY_TOKEN_MAX_AGE=timedelta(seconds=TOKEN_TTL),
        SECURITY_BACKWARDS_COMPAT_AUTH_TOKEN=False,
        SECURITY_BACKWARDS_COMPAT_AUTH_TOKEN_INVALIDATE=True,
        SECURITY_TOKEN_AUTHENTICATION_HEADER="Authentication-Token",
        SECURITY_TOKEN_AUTHENTICATION_KEY="auth_token",
        SECURITY_RETURN_GENERIC_RESPONSES=True,
        SECURITY_CSRF_PROTECT_MECHANISMS=[],
        SECURITY_CSRF_IGNORE_UNAUTH_ENDPOINTS=True,
        SECURITY_FLASH_MESSAGES=False,
        SECURITY_LOGOUT_METHODS=["POST"],
        SESSION_COOKIE_NAME="__Host-task_session",
        SESSION_COOKIE_DOMAIN=None,
        SESSION_COOKIE_PATH="/",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Strict",
        REMEMBER_COOKIE_NAME="__Host-task_remember",
        REMEMBER_COOKIE_DOMAIN=None,
        REMEMBER_COOKIE_PATH="/",
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_SAMESITE="Strict",
        TRUSTED_HOSTS=[
            h.strip()
            for h in os.getenv(
                "TRUSTED_HOSTS", "api.home.arpa,127.0.0.1,localhost"
            ).split(",")
            if h.strip()
        ],
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_REQUEST_BYTES", "2000000")),
    )

    ## ----------------------------------------

    ## Create an adapter for the DB_AUTH connection pool
    db_auth_adapter = DBAuthAdapter(
        db_host=os.getenv("DB_HOST"),
        db_port=os.getenv("DB_PORT"),
        db_name=os.getenv("DB_AUTH_NAME"),
        db_user=os.getenv("DB_AUTH_USER"),
        db_password=read_secret_file("DB_AUTH_PASSWORD_FILE"),
        db_pool_min=os.getenv("DB_POOL_MIN_CONNECTIONS"),
        db_pool_max=os.getenv("DB_POOL_MAX_CONNECTIONS"),
        db_pool_workers=os.getenv("DB_POOL_WORKERS"),
        db_pool_timeout=os.getenv("DB_POOL_TIMEOUT"),
    )

    app.extensions["db_auth_adapter"] = db_auth_adapter
    logging.warning("db_auth_adapter created")

    ## EXIT SAFEGUARD: Close the DB_AUTH connection pool
    atexit.register(db_auth_adapter.close)

    ## ----------------------------------------

    ## Create an adapter for the DB_DATA connection pool
    db_data_adapter = DBDataAdapter(
        db_host=os.getenv("DB_HOST"),
        db_port=os.getenv("DB_PORT"),
        db_name=os.getenv("DB_DATA_NAME"),
        db_user=os.getenv("DB_DATA_USER"),
        db_password=read_secret_file("DB_DATA_PASSWORD_FILE"),
        db_pool_min=os.getenv("DB_POOL_MIN_CONNECTIONS"),
        db_pool_max=os.getenv("DB_POOL_MAX_CONNECTIONS"),
        db_pool_workers=os.getenv("DB_POOL_WORKERS"),
        db_pool_timeout=os.getenv("DB_POOL_TIMEOUT"),
    )

    app.extensions["db_data_adapter"] = db_data_adapter
    logging.warning("db_data_adapter created")

    ## EXIT SAFEGUARD: Close the DB_DATA connection pool
    atexit.register(db_data_adapter.close)

    ## ----------------------------------------

    ## Create an encoder for categorical input data
    feature_encoder = FeatureEncoder(
        encoding_filepath=os.getenv("APPB_FEATURE_ENCODING_FILE")
    )

    app.extensions["feature_encoder"] = feature_encoder
    logging.warning("feature_encoder created")

    ## ----------------------------------------

    ## Create a wrapper for an ML model
    model_wrapper = ModelWrapper(
        model_filepath=os.getenv("APPB_MODEL_FILE"),
        class_names=read_env_list("APPB_MODEL_CLASS_NAMES_LIST"),
    )

    app.extensions["model_wrapper"] = model_wrapper
    logging.warning("model_wrapper created")

    ## ----------------------------------------

    security = Security()
    security.init_app(app, auth_adapter.user_datastore)

    # Trust exactly one proxy hop: Nginx is the only service on the API's edge network.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # Flask-Security owns token creation, signing, expiry and verification. Do not create a parallel JWT.
    # Make login failures JSON-only and avoid redirects or framework exception details for API clients.
    @security.unauthn_handler
    def unauthenticated(mechanisms, headers):
        response = jsonify(error="Authentication required")
        response.status_code = 401
        for key, value in (headers or {}).items():
            response.headers[key] = value
        return response

    ## ----------------------------------------

    # Redis-backed rate limits are shared by all Gunicorn workers and API replicas.
    redis_password = read_secret_file("REDIS_PASSWORD")
    redis_uri = f"redis://:{quote(redis_password, safe='')}@{os.getenv('REDIS_HOST', 'redis')}:6379/0"
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=redis_uri,
        strategy=os.getenv("RATE_LIMIT_STRATEGY", "moving-window"),
        default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120 per minute")],
        application_limits=[os.getenv("RATE_LIMIT_GLOBAL", "600 per minute")],
        meta_limits=[os.getenv("RATE_LIMIT_META", "10 per hour")],
        headers_enabled=os.getenv("RATE_LIMIT_HEADERS_ENABLED", "false").lower()
        == "true",
        key_prefix=os.getenv("RATE_LIMIT_KEY_PREFIX", "secure-task-api"),
        swallow_errors=False,
        in_memory_fallback_enabled=False,
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
    )

    limiter.init_app(app)

    # Flask-Security owns the login endpoint; add a stricter login-specific limit in addition to global limits.
    login_endpoint = app.view_functions.get("security.login")
    if login_endpoint is not None:
        app.view_functions["security.login"] = limiter.limit(
            os.getenv("RATE_LIMIT_LOGIN", "5 per minute")
        )(login_endpoint)

    ## ----------------------------------------

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        return response

    ## ----------------------------------------

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="not_found", message="Resource not found."), 404

    @app.errorhandler(429)
    def too_many(_):
        return jsonify(error="rate_limit_exceeded", message="Too many requests."), 429

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        messages = {
            400: "Bad request",
            401: "Authentication required",
            403: "Forbidden",
            404: "Not found",
            405: "Method not allowed",
            413: "Request too large",
            415: "Unsupported media type",
            429: "Rate limit exceeded",
        }
        return jsonify(error=messages.get(exc.code, "Request failed")), exc.code

    @app.errorhandler(Exception)
    def safe_error(_):
        app.logger.exception("Unhandled API exception")
        return (
            jsonify(
                error="internal_server_error", message="An internal error occurred."
            ),
            500,
        )

    ## ----------------------------------------

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    app.register_blueprint(create_blueprint_auth())
    app.register_blueprint(create_blueprint_private())
    app.register_blueprint(create_blueprint_tasks())

    return app


## ----------------------------------------


def read_secret_file(filepath_var):
    ## Function to read a secret file and return a local variable

    res = None
    try:
        path = Path(os.getenv(filepath_var))
        with open(path, "r") as f:
            res = f.read().strip()

    except Exception as e:
        raise RuntimeError(
            f"Missing or unreadable secret file at {filepath_var}"
        ) from e

    if res:
        return res
    else:
        raise RuntimeError(f"Empty file without a secret at {filepath_var}")


## ----------------------------------------


def read_env_list(list_var, default=None):
    ## Function to read and convert a list from an environmental variable

    res = [
        item.strip(" ")
        for item in str(os.getenv(list_var, "")).strip("([ ])").split(",")
        if item != ""
    ]

    if res:
        return res
    else:
        return default


## ----------------------------------------


def require_roles(*allowed):
    def deco(fn):
        @wraps(fn)
        @auth_required("token")
        def wrapped(*args, **kwargs):
            roles = {role.name for role in current_user.roles}
            if not (roles & set(allowed)):
                return fail("Insufficient permissions", 403)
            g.user_id = str(current_user.id)
            g.user = current_user
            g.roles = roles
            return fn(*args, **kwargs)

        return wrapped

    return deco


def parse_json():
    if not request.is_json:
        raise ValueError("Content-Type must be application/json")
    body = request.get_json(silent=False)
    if not isinstance(body, dict):
        raise ValueError("JSON body must be an object")
    return body


def password_is_strong(password):
    return (
        isinstance(password, str)
        and int(os.getenv("SECURITY_PASSWORD_LENGTH_MIN", "14"))
        <= len(password)
        <= int(os.getenv("SECURITY_PASSWORD_LENGTH_MAX", "128"))
        and zxcvbn(password).get("score", 0)
        >= int(os.getenv("SECURITY_ZXCVBN_MINIMUM_SCORE", "3"))
    )
