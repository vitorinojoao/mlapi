import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

import jwt
from cryptography.hazmat.primitives import serialization

from mlapi.data_preprocessor import DataPreprocessor
from mlapi.data_postprocessor import DataPostprocessor
from mlapi.model_wrapper import ModelWrapper


def create_app():
    """
    Create the Flask Application
    and setup the routes of the API.
    """
    # ------------------------------------------------------------
    # SINGLETONS INITIALIZATION
    # ------------------------------------------------------------

    # Initialize the Data Preprocessor singleton
    DataPreprocessor(
        encoding_filepath=os.getenv("ENCODING_FILEPATH"),
    )

    # Initialize the Data Postprocessor singleton
    DataPostprocessor(
        convert_class_scores=os.getenv("CONVERT_CLASS_SCORES").lower().startswith("t"),
        convert_anomaly_scores=os.getenv("CONVERT_ANOMALY_SCORES")
        .lower()
        .startswith("t"),
        logging_level=int(os.getenv("LOGGING_LEVEL")),
        logging_filepath=os.getenv("LOGGING_FILEPATH"),
    )

    # Initialize the Model Wrapper singleton
    ModelWrapper(
        model_filepath=os.getenv("MODEL_FILEPATH"),
    )

    # ------------------------------------------------------------
    # FLASK INITIALIZATION
    # ------------------------------------------------------------

    # Initialize the Flask Application
    app = Flask(os.getenv("FLASK_APP"))

    # Optional requirement: Cross-Origin Resource Sharing
    if os.getenv("CORS_REQUIRED").lower().startswith("t"):
        CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS")}})

    # Optional requirement: Authorization header
    if os.getenv("AUTH_REQUIRED").lower().startswith("t"):
        try:
            with open(os.getenv("AUTH_PUBLIC_KEY_FILEPATH"), "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
        except Exception:
            raise OSError("Could not load the specified public key file.")

        app.config.update(
            {
                "AUTH_PUBLIC_KEY": public_key,
                "AUTH_ISSUER": os.getenv("AUTH_ISSUER"),
                "AUTH_ALGORITHM": os.getenv("AUTH_ALGORITHM"),
            }
        )

    # ------------------------------------------------------------
    # BASE API SETUP
    # ------------------------------------------------------------

    @app.errorhandler(404)
    def not_found_error(e):
        return (
            "<h1>404 Not Found</h1>"
            + "<p>The resource you're looking for could not be found.</p>",
            404,
        )

    @app.errorhandler(405)
    def not_allowed_error(e):
        return (
            "<h1>405 Method Not Allowed</h1>"
            + "<p>The HTTP method you attempted to use is not allowed for this resource.</p>",
            405,
        )

    @app.errorhandler(Exception)
    def general_error(e):
        if isinstance(e, HTTPException):
            return e

        return (
            "<h1>500 Internal Server Error</h1>"
            + "<p>Something went wrong...<br>"
            + "But it's not you, it's the server.</p>",
            500,
        )

    @app.route("/", methods=["GET", "HEAD"])
    def home_route():
        res = ""
        if request.method == "GET":
            res = "<h1>MLAPI</h1>" + "<p>Welcome to MLAPI.</p>"

        return res, 200

    @app.route("/api/", methods=["GET", "HEAD"])
    def api_route():
        res = ""
        if request.method == "GET":
            res = "<h1>Health Check</h1>" + "<p>All resources are up and running.</p>"

        return res, 200

    # ------------------------------------------------------------
    # MAIN API SETUP
    # ------------------------------------------------------------

    @app.route("/api/ml/", methods=["POST", "GET", "HEAD"])
    def api_ml_route():
        client = None

        # Optional requirement: Authorization header
        if "AUTH_PUBLIC_KEY" in app.config:
            try:
                payload = verify_jwt(
                    request.headers.get("Authorization"),
                    app.config.get("AUTH_PUBLIC_KEY"),
                    app.config.get("AUTH_ISSUER"),
                    app.config.get("AUTH_ALGORITHM"),
                )

                client = payload["sub"]

            except Exception:
                return (
                    "<h1>401 Unauthorized</h1>"
                    + "<p>You are not authorized to access this resource.</p>",
                    401,
                )

        # Deal with GET or HEAD requests
        if request.method == "GET" or request.method == "HEAD":
            res = ""
            if request.method == "GET":
                try:
                    name, classes = ModelWrapper().info()

                    res = (
                        "<h1>ML Model</h1>"
                        + "<p>The utilized model is: {}<br>".format(name)
                        + "The class predictions can be: {}</p>".format(classes)
                    )

                except Exception:
                    return (
                        "<h1>503 Service Unavailable</h1>"
                        + "<p>Could not provide information about the utilized model.</p>",
                        503,
                    )

            return res, 200

        # Deal with POST requests
        try:
            content = request.get_json()

        except Exception:
            return (
                "<h1>400 Bad Request</h1>" + "<p>No JSON content was provided.</p>",
                400,
            )

        try:
            X, n_samples = DataPreprocessor().preprocess(content)
            y = ModelWrapper().predict(X)
            res = DataPostprocessor().postprocess(y, n_samples, client)

            return jsonify(res), 200

        except ValueError as e:
            return "<h1>400 Bad Request</h1>" + "<p>{}</p>".format(e), 400

        except Exception:
            return (
                "<h1>400 Bad Request</h1>"
                + "<p>The JSON content does not have a valid format.</p>",
                400,
            )

    # ------------------------------------------------------------
    # RETURN
    # ------------------------------------------------------------

    return app


def verify_jwt(token, public_key, issuer, algorithm):
    """
    Verify a JWT authorization scheme
    and decode the payload of a signed token.
    """
    # Verify JWT header
    header = jwt.get_unverified_header(token)
    if header["typ"] != "JWT" or header["alg"] != algorithm:
        raise jwt.exceptions.InvalidTokenError("Invalid token.")

    # Verify and decode JWT payload
    return jwt.decode(
        token,
        public_key,
        issuer=issuer,
        algorithms=[algorithm],
        options={"require": ["iss", "iat", "exp", "sub"]},
    )
