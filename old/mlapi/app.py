# MLAPI Template by vitorinojoao

import os
import logging
from flask import Flask, request
from werkzeug.exceptions import HTTPException

from mlapi.blueprint_api import create_api
from mlapi.blueprint_auth import create_auth


def create_app():
    # ---------------------------
    # Load app configuration
    # ---------------------------

    # Create Logging Handler
    logging_level = int(os.getenv("LOGGING_LEVEL", "0"))
    if logging_level > 0:
        logging.basicConfig(
            filename=os.getenv("LOGGING_FILEPATH"),
            filemode="a",
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            level=logging_level,
        )

    # Create Flask Application
    app = Flask(os.getenv("FLASK_APP", "MLAPI"))
    app.config["LOGGING_LEVEL"] = logging_level

    # Enable Cross-Origin Resource Sharing
    if os.getenv("CORS_ENABLED", "t").lower().startswith("t"):
        from flask_cors import CORS

        app.config["CORS_ORIGINS"] = os.getenv("CORS_ORIGINS", "localhost")
        app.config["CORS"] = CORS(
            app, resources={r"/*": {"origins": app.config["CORS_ORIGINS"]}}
        )

    # Enable the AUTH blueprint
    if os.getenv("AUTH_ENABLED", "t").lower().startswith("t"):
        auth_bluep, auth_function = create_auth(
            app=app,
            name_route=os.getenv("AUTH_ROUTE", "auth"),
            logging_level=logging_level,
            clients_registration=dict(
                zip(
                    os.getenv("AUTH_CLIENTS_RESET_USN").split(","),
                    os.getenv("AUTH_CLIENTS_RESET_PWD").split(","),
                )
            ),
            clients_reset_only_once=os.getenv("AUTH_CLIENTS_RESET_ONLY_ONCE")
            .lower()
            .startswith("t"),
            issuer=os.getenv("AUTH_ISSUER", "AS"),
            algorithm=os.getenv("AUTH_ALGORITHM", "RS512"),
            access_ttl_mins=int(os.getenv("AUTH_ACCESS_TTL_MINS", "70")),
            refresh_ttl_mins=int(os.getenv("AUTH_REFRESH_TTL_MINS", "1500")),
            public_key_save_filepath=os.getenv("AUTH_PUBLIC_KEY_SAVE_FILEPATH"),
            private_key_save_filepath=os.getenv("AUTH_PRIVATE_KEY_SAVE_FILEPATH"),
            private_key_save_secret=(
                None
                if os.getenv("AUTH_PRIVATE_KEY_SAVE_SECRET") is None
                else bytes(os.getenv("AUTH_PRIVATE_KEY_SAVE_SECRET"), encoding="utf-8")
            ),
        )

        app.config["AUTH"] = auth_function
        app.register_blueprint(auth_bluep)

    # Enable the API blueprint
    if os.getenv("API_ENABLED", "t").lower().startswith("t"):
        app.register_blueprint(
            create_api(
                app=app,
                name_route=os.getenv("API_ROUTE", "api"),
                logging_level=logging_level,
                auth_function=app.config.get("AUTH"),
                model_filepath=os.getenv("API_MODEL_FILEPATH"),
                convert_class_scores=os.getenv("API_CONVERT_CLASS_SCORES", "t")
                .lower()
                .startswith("t"),
                convert_anomaly_scores=os.getenv("API_CONVERT_ANOMALY_SCORES", "f")
                .lower()
                .startswith("t"),
                encoding_filepath=os.getenv("API_CATEGORICAL_ENCODING_FILEPATH"),
            )
        )

    # ------------------------------
    # Define app default routes
    # ------------------------------

    @app.errorhandler(404)
    def error_not_found(e):
        return (
            "<h1>404 Not Found</h1>"
            + "<p>The resource you're looking for could not be found.</p>",
            404,
        )

    @app.errorhandler(405)
    def error_not_allowed(e):
        return (
            "<h1>405 Method Not Allowed</h1>"
            + "<p>The HTTP method you attempted to use is not allowed for this resource.</p>",
            405,
        )

    @app.errorhandler(Exception)
    def error_general(e):
        if isinstance(e, HTTPException):
            return e

        return (
            "<h1>500 Internal Server Error</h1>"
            + "<p>Something went wrong...<br>"
            + "But it's not you, it's the server.</p>",
            500,
        )

    @app.route("/", methods=["GET", "HEAD"])
    def route_home():
        if request.method == "HEAD":
            return "", 200

        return "<h1>Health Check</h1>" + "<p>Resources are up and running.</p>", 200

    return app


# End of MLAPI Template by vitorinojoao
