import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, g
from flask_security import hash_password
from psycopg.types.json import Jsonb
from api.app import db, User, datastore, ROLE_NAMES, cfg_conn, data_conn, fail, parse_json, normalize_email, password_is_strong, require_roles, limiter

admin_bp = Blueprint("admin_api", __name__, url_prefix="/admin")

@admin_bp.before_request
def reject_url_tokens_and_non_json_mutations():
    if "auth_token" in request.args:
        return jsonify(error="Tokens must be sent in the Authentication-Token header"), 400
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.is_json:
        return jsonify(error="Content-Type must be application/json"), 415

@admin_bp.get("/tasks")
@limiter.limit(os.getenv("RATE_LIMIT_ADMIN_READS", "30 per minute"))
@require_roles("privileged", "admin")
def all_task_timestamps():
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("SELECT task_id,user_id,created_at,status FROM pending_tasks ORDER BY created_at")
        pending = [{**r, "task_id": str(r["task_id"]), "created_at": r["created_at"].isoformat()} for r in cur.fetchall()]
        cur.execute("SELECT task_id,user_id,created_at,completed_at,status FROM completed_tasks ORDER BY completed_at DESC")
        completed = [{**r, "task_id": str(r["task_id"]), "created_at": r["created_at"].isoformat(), "completed_at": r["completed_at"].isoformat()} for r in cur.fetchall()]
    return jsonify(pending=pending, completed=completed)

@admin_bp.get("/users/<user_id>/tasks")
@limiter.limit(os.getenv("RATE_LIMIT_ADMIN_READS", "30 per minute"))
@require_roles("privileged", "admin")
def user_task_timestamps(user_id):
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("SELECT task_id,created_at,status FROM pending_tasks WHERE user_id=%s ORDER BY created_at", (user_id,)); pending = cur.fetchall()
        cur.execute("SELECT task_id,created_at,completed_at,status FROM completed_tasks WHERE user_id=%s ORDER BY completed_at DESC", (user_id,)); completed = cur.fetchall()
    fmt = lambda rows: [{k: (v.isoformat() if isinstance(v, datetime) else str(v) if k == "task_id" else v) for k, v in r.items()} for r in rows]
    return jsonify(pending=fmt(pending), completed=fmt(completed))

@admin_bp.post("/users")
@limiter.limit(os.getenv("RATE_LIMIT_ADMIN_MUTATIONS", "10 per minute"))
@require_roles("admin")
def create_user():
    try: body = parse_json()
    except Exception: return fail("Invalid JSON request", 400)
    email, password, role = normalize_email(body.get("email")), body.get("password"), body.get("role")
    if not email or not password_is_strong(password) or role not in ROLE_NAMES or role == "admin": return fail("Valid email, strong password, and non-admin role required", 400)
    if datastore.find_user(email=email): return fail("Email already exists", 409)
    user = datastore.create_user(email=email, password=hash_password(password), active=True, confirmed_at=datetime.now(timezone.utc))
    datastore.add_role_to_user(user, role); db.session.commit()
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO user_directory(user_id,email) VALUES (%s,%s) ON CONFLICT(user_id) DO UPDATE SET email=EXCLUDED.email", (str(user.id), email))
        cur.execute("INSERT INTO user_audit(user_id,action,details) VALUES (%s,'user_created',%s)", (str(user.id), Jsonb({"by_user_id": g.user_id, "role": role})))
    return jsonify(user_id=user.id, email=email, role=role), 201

@admin_bp.post("/config")
@limiter.limit(os.getenv("RATE_LIMIT_ADMIN_MUTATIONS", "10 per minute"))
@require_roles("admin")
def update_config():
    try:
        b = parse_json(); workers = int(b["worker_count"]); order = b["task_order"]; sleep = int(b["worker_sleep_seconds"]); pending = int(b["pending_ttl_seconds"]); completed = int(b["completed_ttl_seconds"])
    except Exception: return fail("Required configuration fields are missing or invalid", 400)
    if not 1 <= workers <= 32 or order not in ("oldest", "newest") or not 1 <= sleep <= 3600 or pending < 0 or completed < 0: return fail("Configuration values out of range", 400)
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO system_config(worker_count,task_order,worker_sleep_seconds,pending_ttl_seconds,completed_ttl_seconds) VALUES (%s,%s,%s,%s,%s) RETURNING config_id,created_at", (workers, order, sleep, pending, completed)); r = cur.fetchone()
    return jsonify(config_id=r["config_id"], created_at=r["created_at"].isoformat()), 201

@admin_bp.post("/users/<int:target_id>/remove")
@limiter.limit(os.getenv("RATE_LIMIT_ADMIN_MUTATIONS", "10 per minute"))
@require_roles("admin")
def remove_user(target_id):
    if target_id == g.user.id: return fail("Cannot remove the current admin account", 400)
    target = db.session.get(User, target_id)
    if not target: return fail("User not found", 404)
    if any(r.name == "admin" for r in target.roles): return fail("Admin users cannot be removed through this endpoint", 403)
    uid = str(target.id)
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO user_audit(user_id,action,details) VALUES (%s,'user_removed',%s)", (uid, Jsonb({"by_user_id": g.user_id, "email": target.email})))
        cur.execute("UPDATE user_directory SET removed_at=now() WHERE user_id=%s", (uid,))
        cur.execute("UPDATE pending_tasks SET status='failed',error_code='user_removed' WHERE user_id=%s", (uid,))
    with data_conn() as c, c.cursor() as cur:
        cur.execute("DELETE FROM task_data WHERE user_id=%s RETURNING data_id,results_id", (uid,)); links = cur.fetchall()
        for link in links:
            if link["results_id"]: cur.execute("DELETE FROM results WHERE results_id=%s", (link["results_id"],))
            cur.execute("DELETE FROM samples WHERE data_id=%s", (link["data_id"],))
    db.session.delete(target); db.session.commit()
    return jsonify(status="user_removed", user_id=uid, retained_config_audit=True)
