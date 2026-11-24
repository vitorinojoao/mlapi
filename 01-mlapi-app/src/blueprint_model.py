"""blueprint_model"""

from flask import Blueprint, current_app, request, jsonify
from flask_security import auth_required, roles_accepted


def create_blueprint_model(
    app,
    limiter,
    feature_encoder,
    model_wrapper,
):
    bp = Blueprint("model", __name__, url_prefix="/model")

    app.extensions["bp_model_f_encoder"] = feature_encoder
    app.extensions["bp_model_m_wrapper"] = model_wrapper

    ## ----------------------------------------

    @bp.get("/")
    ## General limits can be overriden with a custom limit in each route
    ## @limiter.limit("120 per minute")
    @auth_required("token")
    @roles_accepted("consumer")
    def head_model():
        return jsonify(status="ok")

    ## ----------------------------------------

    @bp.get("/info")
    @auth_required("token")
    @roles_accepted("consumer")
    def get_model_info():
        try:
            return jsonify(current_app.extensions["bp_model_m_wrapper"].info())
        except Exception:
            return (
                "<h1>503 Service Unavailable</h1>"
                + "<p>Could not provide information about the utilized model.</p>",
                503,
            )

    ## ----------------------------------------

    @bp.post("/predict")
    @auth_required("token")
    @roles_accepted("consumer")
    def post_model_predict():
        try:
            content = request.get_json()
        except Exception:
            return (
                "<h1>400 Bad Request</h1>" + "<p>No JSON content was provided.</p>",
                400,
            )

        try:
            samples, n_samples = current_app.extensions[
                "bp_model_f_encoder"
            ].preprocess(content, create_array=True)

            y = current_app.extensions["bp_model_m_wrapper"].predict(samples)

            res = current_app.extensions["bp_model_m_wrapper"].postprocess_class_scores(
                y, n_samples
            )
            return jsonify(res)

        except ValueError as e:
            return "<h1>400 Bad Request</h1>" + "<p>{}</p>".format(e), 400

        except Exception:
            return (
                "<h1>400 Bad Request</h1>"
                + "<p>The JSON content does not have a valid format.</p>",
                400,
            )

    ## ----------------------------------------

    app.register_blueprint(bp)
