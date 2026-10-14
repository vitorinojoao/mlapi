import os
from flask import Blueprint, current_app, jsonify, request, current_user
from flask_security import auth_required, hash_password
from psycopg.types.json import Jsonb
from api.app import datastore, cfg_conn, parse_json, fail, normalize_email, password_is_strong, limiter

auth_bp = Blueprint("auth_api", __name__, url_prefix="/auth")

@auth_bp.before_request
def require_json_for_mutations():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.is_json:
        return jsonify(error="Content-Type must be application/json"), 415
    if "auth_token" in request.args:
        return jsonify(error="Tokens must be sent in the Authentication-Token header"), 400

@auth_bp.post("/email")
@limiter.limit(os.getenv("RATE_LIMIT_CREDENTIAL_CHANGES", "5 per hour"))
@auth_required("token", within=5)
def change_email():
    try: body = parse_json()
    except (ValueError, Exception): return fail("Invalid JSON request", 400)
    email = normalize_email(body.get("email"))
    if not email: return fail("Valid email required", 400)
    existing = datastore.find_user(email=email)
    if existing and existing.id != current_user.id: return fail("Email already in use", 409)
    current_user.email = email
    datastore.set_uniquifier(current_user)
    datastore.commit()
    with cfg_conn() as c, c.cursor() as cur:
        cur.execute("UPDATE user_directory SET email=%s WHERE user_id=%s", (email, str(current_user.id)))
        cur.execute("INSERT INTO user_audit(user_id,action,details) VALUES (%s,'email_changed',%s)", (str(current_user.id), Jsonb({"by_user_id": str(current_user.id)})))
    return jsonify(status="email_changed", reauthenticate=True)

@auth_bp.post("/password")
@limiter.limit(os.getenv("RATE_LIMIT_CREDENTIAL_CHANGES", "5 per hour"))
@auth_required("token", within=5)
def change_password_api():
    try: body = parse_json()
    except Exception: return fail("Invalid JSON request", 400)
    old_password, new_password = body.get("current_password"), body.get("new_password")
    if not isinstance(old_password, str) or not isinstance(new_password, str): return fail("current_password and new_password are required", 400)
    if not current_user.verify_and_update_password(old_password): return fail("Invalid credentials", 401)
    if not password_is_strong(new_password): return fail("New password does not meet password policy", 400)
    current_user.password = hash_password(new_password)
    datastore.set_uniquifier(current_user)
    datastore.commit()
    return jsonify(status="password_changed", reauthenticate=True)

@auth_bp.post("/token/logout")
@limiter.limit(os.getenv("RATE_LIMIT_AUTH_MUTATIONS", "20 per minute"))
@auth_required("token")
def logout_token():
    datastore.set_uniquifier(current_user)
    datastore.commit()
    return jsonify(status="logged_out")
