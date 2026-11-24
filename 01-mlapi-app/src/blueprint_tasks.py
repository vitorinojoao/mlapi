"""blueprint_tasks"""

from flask import Blueprint, current_app, request, jsonify
from flask_security import auth_required, roles_accepted, current_user


def create_blueprint_tasks(
    app,
    limiter,
    db_data_adapter,
    feature_encoder,
):
    bp = Blueprint("tasks", __name__, url_prefix="/tasks")

    app.extensions["bp_tasks_db_data"] = db_data_adapter
    app.extensions["bp_tasks_f_encoder"] = feature_encoder

    ## ----------------------------------------

    @bp.get("/")
    ## General limits can be overriden with a custom limit in each route
    ## @limiter.limit("120 per minute")
    @auth_required("token")
    @roles_accepted("consumer, provider")
    def head_tasks():
        return jsonify(status="ok")

    ## ----------------------------------------

    @bp.get("/status/<task_id>")
    @auth_required("token")
    @roles_accepted("consumer")
    def get_tasks_status(task_id):
        try:
            res = current_app.extensions["bp_tasks_db_data"].check_task_status(
                current_user.id, task_id
            )
        except Exception:
            # current_app.logger.exception("Database error")
            return (
                jsonify(error="storage_unavailable", message="Database error."),
                503,
            )

        if res is None:
            return jsonify(error="not_found", message="Task not found."), 404

        return jsonify(
            created_at=res[0].isoformat(),
            claimed_at=res[1].isoformat() if res[1] else "",
            done_at=res[2].isoformat() if res[2] else "",
            done_success=bool(res[3]),
            done_message=res[4] if res[4] else "",
        )

    ## ----------------------------------------

    @bp.get("/out/<task_id>")
    @auth_required("token")
    @roles_accepted("consumer")
    def get_tasks_output(task_id):
        try:
            res = current_app.extensions["bp_tasks_db_data"].fetch_task_results(
                current_user.id, task_id
            )
        except Exception:
            # current_app.logger.exception("Database error")
            return (
                jsonify(error="storage_unavailable", message="Database error."),
                503,
            )

        if res is None:
            return jsonify(error="not_found", message="Task not found."), 404

        return jsonify(res)

    ## ----------------------------------------

    @bp.post("/in")
    @auth_required("token")
    @roles_accepted("provider")
    def post_tasks_input():
        try:
            content = request.get_json()
        except Exception:
            return (
                jsonify(error="invalid_request", message="No input samples."),
                400,
            )

        try:
            samples, _ = current_app.extensions["bp_model_f_encoder"].preprocess(
                content, create_array=True
            )
        except Exception:
            return (
                jsonify(error="invalid_request", message="Input samples are invalid."),
                400,
            )

        try:
            task_id = current_app.extensions["bp_tasks_db_data"].register_pending_task(
                current_user.id, samples
            )
            return jsonify(task_id=task_id), 201

        except Exception:
            # current_app.logger.exception("Database error")
            return (
                jsonify(error="storage_unavailable", message="Database error."),
                503,
            )

    ## ----------------------------------------

    app.register_blueprint(bp)
