import os, uuid
from datetime import datetime
from flask import Blueprint, current_app, jsonify, request, g
from flask_security import auth_required
from psycopg.types.json import Jsonb
from api.app import cfg_conn, data_conn, fail, parse_json, require_roles, limiter

users_bp = Blueprint("users_api", __name__)

@users_bp.before_request
def reject_url_tokens_and_non_json_mutations():
    if "auth_token" in request.args:
        return jsonify(error="Tokens must be sent in the Authentication-Token header"), 400
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.is_json:
        return jsonify(error="Content-Type must be application/json"), 415

@users_bp.post("/tasks")
@limiter.limit(os.getenv("RATE_LIMIT_TASK_SUBMIT", "10 per minute"))
@require_roles("provider", "prosumer")
def submit_task():
    try: body = parse_json()
    except Exception: return fail("Invalid JSON request", 400)
    samples = body.get("samples")
    if not isinstance(samples, (list, dict)) or not samples: return fail("samples must be a non-empty JSON array or object", 400)
    if len(request.get_data()) > int(os.getenv("MAX_REQUEST_BYTES", "2000000")): return fail("Request too large", 413)
    task_id, data_id, uid = uuid.uuid4(), uuid.uuid4(), g.user_id
    try:
        with cfg_conn() as c, c.cursor() as cur:
            cur.execute("INSERT INTO pending_tasks(task_id,user_id,status) VALUES (%s,%s,'pending')", (task_id, uid))
            cur.execute("INSERT INTO submission_outbox(task_id,user_id,state) VALUES (%s,%s,'pending')", (task_id, uid))
        with data_conn() as c, c.cursor() as cur:
            cur.execute("INSERT INTO samples(data_id,samples) VALUES (%s,%s)", (data_id, Jsonb(samples)))
            cur.execute("INSERT INTO task_data(task_id,user_id,data_id) VALUES (%s,%s,%s)", (task_id, uid, data_id))
        with cfg_conn() as c, c.cursor() as cur: cur.execute("UPDATE submission_outbox SET state='complete' WHERE task_id=%s", (task_id,))
    except Exception as exc:
        current_app.logger.error("Task submission failed task_id=%s type=%s", task_id, type(exc).__name__)
        return fail("Submission could not be completed; retry after checking task status", 503)
    return jsonify(task_id=str(task_id)), 201

@users_bp.get("/tasks/<uuid:task_id>")
@limiter.limit(os.getenv("RATE_LIMIT_READS", "120 per minute"))
@require_roles("consumer", "prosumer")
def task_status(task_id):
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("SELECT task_id,user_id,status,created_at FROM pending_tasks WHERE task_id=%s", (task_id,)); row = cur.fetchone()
        if not row:
            cur.execute("SELECT task_id,user_id,status,created_at,completed_at FROM completed_tasks WHERE task_id=%s", (task_id,)); row = cur.fetchone()
    if not row: return fail("Task not found", 404)
    if row["user_id"] != g.user_id and not (g.roles & {"admin", "privileged"}): return fail("Task not found", 404)
    result = {k: (v.isoformat() if isinstance(v, datetime) else str(v) if k == "task_id" else v) for k, v in row.items()}
    if row.get("status") == "completed":
        with data_conn() as c, c.cursor() as cur:
            cur.execute("SELECT r.result FROM task_data td JOIN results r ON r.results_id=td.results_id WHERE td.task_id=%s", (task_id,)); rr = cur.fetchone()
        result["result"] = rr["result"] if rr else None
    return jsonify(result)

@users_bp.get("/results")
@limiter.limit(os.getenv("RATE_LIMIT_READS", "120 per minute"))
@require_roles("consumer", "prosumer")
def completed_results():
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("SELECT task_id,created_at,completed_at FROM completed_tasks WHERE user_id=%s ORDER BY completed_at DESC LIMIT 500", (g.user_id,)); tasks = cur.fetchall()
    out = []
    with data_conn() as c, c.cursor() as cur:
        for t in tasks:
            cur.execute("SELECT r.result FROM task_data td JOIN results r ON r.results_id=td.results_id WHERE td.task_id=%s", (t["task_id"],)); r = cur.fetchone()
            out.append({"task_id": str(t["task_id"]), "created_at": t["created_at"].isoformat(), "completed_at": t["completed_at"].isoformat(), "result": r["result"] if r else None})
    return jsonify(results=out)
