"""blueprint_auth"""

from flask import Blueprint, current_app, request, jsonify
from flask_security import auth_required, current_user, hash_password


def create_blueprint_auth(
    app,
    limiter,
    db_auth_adapter,
):
    bp = Blueprint("auth", __name__, url_prefix="/auth")

    app.extensions["bp_auth_db_auth"] = db_auth_adapter

    ## ----------------------------------------

    @bp.get("/")
    @limiter.limit("20 per minute")
    @auth_required("token")
    def head_auth():
        return jsonify(status="ok")

    ## ----------------------------------------

    @auth_bp.post("/token/logout")
    @limiter.limit("20 per minute")
    @auth_required("token")
    def logout_token():
        datastore.set_uniquifier(current_user)
        datastore.commit()
        return jsonify(status="logged_out")

    @auth_bp.post("/password")
    @limiter.limit("10 per hour")
    @auth_required("token", within=5)
    def change_password_api():
        try:
            body = parse_json()
        except Exception:
            return fail("Invalid JSON request", 400)
        old_password, new_password = body.get("current_password"), body.get(
            "new_password"
        )
        if not isinstance(old_password, str) or not isinstance(new_password, str):
            return fail("current_password and new_password are required", 400)
        if not current_user.verify_and_update_password(old_password):
            return fail("Invalid credentials", 401)
        if not password_is_strong(new_password):
            return fail("New password does not meet password policy", 400)
        current_user.password = hash_password(new_password)
        datastore.set_uniquifier(current_user)
        datastore.commit()
        return jsonify(status="password_changed", reauthenticate=True)

    ## ----------------------------------------

    app.register_blueprint(bp)
