import os, uuid
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import Flask, jsonify, request, g, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from email_validator import validate_email, EmailNotValidError
from sqlalchemy.engine import URL
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from urllib.parse import quote
import redis as redis_client
from flask_security import (
    Security, SQLAlchemyUserDatastore, UserMixin, RoleMixin,
    auth_required, hash_password,
)
from psycopg.types.json import Jsonb
from zxcvbn import zxcvbn
from shared.common import secret, connect, retry_init

app = Flask(__name__)
TOKEN_TTL = max(60, min(int(os.getenv("SECURITY_TOKEN_TTL_SECONDS", "900")), 3600))

APP_EXTERNAL_URL_1 = os.environ["APP_EXTERNAL_URL_1"].rstrip("/")
APP_EXTERNAL_URL_2 = os.environ["APP_EXTERNAL_URL_2"].rstrip("/")

app.config.update(
    SECRET_KEY=secret("FLASK_SECRET_KEY"),
    SECURITY_PASSWORD_SALT=secret("SECURITY_PASSWORD_SALT"),
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
    SECURITY_PASSWORD_LENGTH_MIN=int(os.getenv("SECURITY_PASSWORD_LENGTH_MIN", "14")),
    SECURITY_PASSWORD_COMPLEXITY_CHECKER="zxcvbn",
    SECURITY_ZXCVBN_MINIMUM_SCORE=int(os.getenv("SECURITY_ZXCVBN_MINIMUM_SCORE", "3")),
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
    TRUSTED_HOSTS=[h.strip() for h in os.getenv("TRUSTED_HOSTS", "api.home.arpa,127.0.0.1,localhost").split(",") if h.strip()],
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    MAX_CONTENT_LENGTH=int(os.getenv("MAX_REQUEST_BYTES", "2000000")),
)
# Redis-backed rate limits are shared by all Gunicorn workers and API replicas.
redis_password = secret("REDIS_PASSWORD")
redis_uri = f"redis://:{quote(redis_password, safe='')}@{os.getenv('REDIS_HOST', 'redis')}:6379/0"
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_uri,
    strategy=os.getenv("RATE_LIMIT_STRATEGY", "moving-window"),
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120 per minute")],
    application_limits=[os.getenv("RATE_LIMIT_GLOBAL", "600 per minute")],
    meta_limits=[os.getenv("RATE_LIMIT_META", "10 per hour")],
    headers_enabled=os.getenv("RATE_LIMIT_HEADERS_ENABLED", "false").lower() == "true",
    key_prefix=os.getenv("RATE_LIMIT_KEY_PREFIX", "secure-task-api"),
    swallow_errors=False,
    in_memory_fallback_enabled=False,
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
)

# Trust exactly one proxy hop: Nginx is the only service on the API's edge network.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# The auth database connection URL is assembled from Docker secrets and is never logged.
auth_user, auth_password = secret("AUTH_DB_USER"), secret("AUTH_DB_PASSWORD")
app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
    "postgresql+psycopg", username=auth_user, password=auth_password,
    host=os.getenv("DB_HOST", "db"), port=5432, database="auth"
)
db = SQLAlchemy(app)

roles_users = db.Table("roles_users", db.metadata,
    db.Column("user_id", db.Integer(), db.ForeignKey("user.id"), primary_key=True),
    db.Column("role_id", db.Integer(), db.ForeignKey("role.id"), primary_key=True))
class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
class User(db.Model, UserMixin):
    id = db.Column(db.Integer(), primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean(), nullable=False, default=True)
    fs_uniquifier = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    confirmed_at = db.Column(db.DateTime(timezone=True))
    failed_login_count = db.Column(db.Integer(), nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    roles = db.relationship("Role", secondary=roles_users, backref=db.backref("users", lazy="dynamic"))

    @property
    def user_id(self):
        return str(self.id)

    def track_failed_authn(self, auth_type, tfa=False):
        # Flask-Security calls this hook when a credential is invalid.
        self.failed_login_count = (self.failed_login_count or 0) + 1
        threshold = max(1, int(os.getenv("AUTH_FAILURE_LOCKOUT_THRESHOLD", "5")))
        if self.failed_login_count >= threshold:
            seconds = max(30, int(os.getenv("AUTH_FAILURE_LOCKOUT_SECONDS", "900")))
            self.locked_until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        db.session.commit()
        super().track_failed_authn(auth_type, tfa=tfa)

    def is_locked(self, form_error=None):
        # Flask-Security consults this hook during authentication.
        if self.locked_until is None:
            return False
        now = datetime.now(timezone.utc)
        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            return True
        self.failed_login_count = 0
        self.locked_until = None
        db.session.commit()
        return False

datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, datastore)
limiter.init_app(app)

# Flask-Security owns token creation, signing, expiry and verification. Do not create a parallel JWT.
# Make login failures JSON-only and avoid redirects or framework exception details for API clients.
@security.unauthn_handler
def unauthenticated(mechanisms, headers):
    response = jsonify(error="Authentication required")
    response.status_code = 401
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response

ROLE_NAMES = {"provider", "consumer", "prosumer", "privileged", "admin"}


def credentials(prefix):
    return secret(prefix + "_DB_USER"), secret(prefix + "_DB_PASSWORD")
def cfg_conn():
    u,p=credentials("CONFIG"); return connect("config",u,p)
def data_conn():
    u,p=credentials("DATA"); return connect("data",u,p)
def auth_conn():
    u,p=credentials("AUTH"); return connect("auth",u,p)


def init_databases():
    with app.app_context():
        db.create_all()
        # Lightweight additive migration for existing deployments.
        with db.engine.begin() as conn:
            conn.exec_driver_sql('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0')
            conn.exec_driver_sql('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ NULL')
        for name in sorted(ROLE_NAMES):
            if not datastore.find_role(name): datastore.create_role(name=name, description=f"{name} role")
        admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@example.invalid").strip().lower()
        initial_password = secret("INITIAL_ADMIN_PASSWORD")
        user = datastore.find_user(email=admin_email)
        if not user:
            user = datastore.create_user(email=admin_email, password=hash_password(initial_password), active=True, confirmed_at=datetime.now(timezone.utc))
            datastore.add_role_to_user(user, "admin")
        db.session.commit()
        with cfg_conn() as c, c.cursor() as cur:
            cur.execute("INSERT INTO user_directory(user_id,email) VALUES (%s,%s) ON CONFLICT(user_id) DO UPDATE SET email=EXCLUDED.email", (str(user.id), user.email))
    # Config/data schema migrations are safe to re-run. Do not store passwords in these databases.
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS system_config (
            config_id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            worker_count INT NOT NULL CHECK(worker_count BETWEEN 1 AND 32),
            task_order TEXT NOT NULL CHECK(task_order IN ('oldest','newest')),
            worker_sleep_seconds INT NOT NULL CHECK(worker_sleep_seconds BETWEEN 1 AND 3600),
            pending_ttl_seconds BIGINT NOT NULL CHECK(pending_ttl_seconds >= 0),
            completed_ttl_seconds BIGINT NOT NULL CHECK(completed_ttl_seconds >= 0));
            CREATE TABLE IF NOT EXISTS pending_tasks (
            task_id UUID PRIMARY KEY, user_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','processing','failed')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), error_code TEXT);
            CREATE TABLE IF NOT EXISTS completed_tasks (
            task_id UUID PRIMARY KEY, user_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ NOT NULL, status TEXT NOT NULL DEFAULT 'completed');
            CREATE TABLE IF NOT EXISTS user_directory (
            user_id TEXT PRIMARY KEY, email TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), removed_at TIMESTAMPTZ);
            CREATE TABLE IF NOT EXISTS user_audit (
            audit_id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, action TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(), details JSONB NOT NULL DEFAULT '{}'::jsonb);
            CREATE TABLE IF NOT EXISTS submission_outbox (
            task_id UUID PRIMARY KEY, user_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now());""")
        cur.execute("SELECT count(*) AS n FROM system_config")
        if cur.fetchone()["n"] == 0:
            cur.execute("INSERT INTO system_config(worker_count,task_order,worker_sleep_seconds,pending_ttl_seconds,completed_ttl_seconds) VALUES (%s,%s,%s,%s,%s)", (int(os.getenv("WORKER_COUNT","2")),"oldest",5,86400*7,86400*30))
    with data_conn() as c, c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS samples (
            data_id UUID PRIMARY KEY, samples JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
            CREATE TABLE IF NOT EXISTS results (
            results_id UUID PRIMARY KEY, result JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
            CREATE TABLE IF NOT EXISTS task_data (
            task_id UUID PRIMARY KEY, user_id TEXT NOT NULL, data_id UUID NOT NULL REFERENCES samples(data_id),
            results_id UUID REFERENCES results(results_id), created_at TIMESTAMPTZ NOT NULL DEFAULT now());""")

retry_init(init_databases)


def fail(message, status):
    return jsonify(error=message), status

@app.before_request
def enforce_api_only_and_reject_url_tokens():
    # API-only: never render Flask-Security forms or accept browser form submissions.
    if request.endpoint and request.endpoint.startswith("security.") and request.method == "GET":
        return jsonify(error="Method not allowed"), 405
    if request.endpoint and request.endpoint.startswith("security.") and request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.is_json:
        return jsonify(error="Content-Type must be application/json"), 415
    # URL tokens leak through access logs, browser history, referrers, and monitoring.
    if "auth_token" in request.args:
        return jsonify(error="Send authentication tokens in the Authentication-Token header"), 400

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
        and int(os.getenv("SECURITY_PASSWORD_LENGTH_MIN", "14")) <= len(password) <= int(os.getenv("SECURITY_PASSWORD_LENGTH_MAX", "128"))
        and zxcvbn(password).get("score", 0) >= int(os.getenv("SECURITY_ZXCVBN_MINIMUM_SCORE", "3"))
    )

def normalize_email(value):
    if not isinstance(value, str) or len(value) > 255:
        return None
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None

@app.errorhandler(HTTPException)
def handle_http_error(exc):
    messages = {400: "Bad request", 401: "Authentication required", 403: "Forbidden", 404: "Not found", 405: "Method not allowed", 413: "Request too large", 415: "Unsupported media type", 429: "Rate limit exceeded"}
    return jsonify(error=messages.get(exc.code, "Request failed")), exc.code

@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    app.logger.error("Unhandled request failure type=%s path=%s", type(exc).__name__, request.path)
    return jsonify(error="Internal server error"), 500

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/ready")
def ready():
    try:
        with cfg_conn() as c, c.cursor() as cur: cur.execute("SELECT 1")
        with data_conn() as c, c.cursor() as cur: cur.execute("SELECT 1")
        with auth_conn() as c, c.cursor() as cur: cur.execute("SELECT 1")
        redis_client.Redis.from_url(redis_uri, socket_connect_timeout=1, socket_timeout=1).ping()
        return jsonify(status="ready")
    except Exception as exc:
        app.logger.warning("Readiness check failed type=%s", type(exc).__name__)
        return jsonify(status="not_ready"), 503

def fetch_external_status():
    response = http.get(
        APP_EXTERNAL_URL_1 + "/status",
        timeout=(3, 10),
        allow_redirects=False,
    )
    response.raise_for_status()
    return response.json()

# Route groups are separate modules and blueprints to keep auth, user, and admin surfaces isolated.
from api.routes.auth import auth_bp
from api.routes.users import users_bp
from api.routes.admin import admin_bp
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(admin_bp)

# Flask-Security owns the login endpoint; add a stricter login-specific limit in addition to global limits.
login_endpoint = app.view_functions.get("security.login")
if login_endpoint is not None:
    app.view_functions["security.login"] = limiter.limit(os.getenv("RATE_LIMIT_LOGIN", "5 per minute"))(login_endpoint)

if __name__ == "__main__": app.run(host="0.0.0.0",port=8000)
