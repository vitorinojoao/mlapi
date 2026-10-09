# MLAPI Template by vitorinojoao

from flask import Blueprint, current_app, request, jsonify

from mlapi.data_preprocessor import DataPreprocessor
from mlapi.data_postprocessor import DataPostprocessor
from mlapi.model_wrapper import ModelWrapper


def create_api(
    app,
    name_route,
    logging_level,
    auth_function,
    model_filepath,
    convert_class_scores=True,
    convert_anomaly_scores=False,
    encoding_filepath=None,
):
    # ---------------------------
    # Load API configuration
    # ---------------------------

    name_route = str(name_route).lower()
    bluep = Blueprint(name_route, __name__, url_prefix=f"/{name_route}")

    dpre = DataPreprocessor(
        logging_level=logging_level,
        encoding_filepath=encoding_filepath,
    )

    dpost = DataPostprocessor(
        logging_level=logging_level,
        convert_class_scores=convert_class_scores,
        convert_anomaly_scores=convert_anomaly_scores,
    )

    mwrap = ModelWrapper(model_filepath=model_filepath)

    app.config["API_CONFIG"] = {
        "NAME_ROUTE": name_route,
        "LOGGING_LEVEL": logging_level,
        # -----
        "AUTH": auth_function,
        # -----
        "DATA_PREPROCESSOR": dpre,
        "DATA_POSTPROCESSOR": dpost,
        "MODEL_WRAPPER": mwrap,
    }

    # ----------------------
    # Define API routes
    # ----------------------

    @bluep.route("/", methods=["GET", "HEAD"])
    def route_api():
        if request.method == "HEAD":
            return "", 200

        name_route = current_app.config["API_CONFIG"]["NAME_ROUTE"]
        return (
            "<h1>Health Check</h1>"
            + f"<p>Resources of '{name_route}' are up and running.</p>",
            200,
        )

    @bluep.route("/ml/", methods=["GET", "POST"])
    def route_api_ml():
        conf = current_app.config["API_CONFIG"]

        # Validate request and obtain client
        try:
            conf["AUTH"](request)

        except Exception:
            return (
                "<h1>401 Unauthorized</h1>"
                + "<p>You are not authorized to access this resource.</p>",
                401,
            )

        # Deal with GET request
        if request.method == "GET":
            try:
                name, classes = conf["MODEL_WRAPPER"].info()

                return (
                    "<h1>ML Model</h1>"
                    + "<p>The utilized model is: {}<br>".format(name)
                    + "The class predictions can be: {}</p>".format(classes)
                ), 200

            except Exception:
                return (
                    "<h1>503 Service Unavailable</h1>"
                    + "<p>Could not provide information about the utilized model.</p>",
                    503,
                )

        # Deal with POST request
        try:
            content = request.get_json()

        except Exception:
            return (
                "<h1>400 Bad Request</h1>" + "<p>No JSON content was provided.</p>",
                400,
            )

        try:
            X, n_samples = conf["DATA_PREPROCESSOR"].preprocess(content)
            y = conf["MODEL_WRAPPER"].predict(X)
            res = conf["DATA_POSTPROCESSOR"].postprocess(y, n_samples)

            return jsonify(res), 200

        except ValueError as e:
            return "<h1>400 Bad Request</h1>" + "<p>{}</p>".format(e), 400

        except Exception:
            return (
                "<h1>400 Bad Request</h1>"
                + "<p>The JSON content does not have a valid format.</p>",
                400,
            )

    return bluep


# End of MLAPI Template by vitorinojoao
