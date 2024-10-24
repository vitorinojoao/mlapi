# MLAPI Template by vitorinojoao

# ---------------------------
# Command-Line Interface
# ---------------------------

if __name__ == "__main__":
    from argparse import ArgumentParser, ArgumentTypeError, RawTextHelpFormatter

    parser = ArgumentParser(
        description="Run a stand-alone development server",
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="whether to activate the debug mode",
    )

    def check_address(value):
        try:
            temp = value.split(".")
            if len(temp) != 4:
                raise Exception()

        except:
            raise ArgumentTypeError(
                "Invalid option for -b, --bind argument."
                + " Repeat with only --help to see the valid options."
            )
        return value

    def check_port(value):
        try:
            ivalue = int(value)
            if ivalue <= 0:
                raise Exception()

        except:
            raise ArgumentTypeError(
                "Invalid option for -p, --port argument."
                + " Repeat with only --help to see the valid options."
            )
        return ivalue

    requiredNamed = parser.add_argument_group("required named arguments")

    requiredNamed.add_argument(
        "-a",
        "--address",
        nargs=1,
        type=check_address,
        metavar="IPAddress",
        dest="flask_host",
        help="the IP address for the server (e.g. 127.0.0.1)",
        required=True,
    )

    requiredNamed.add_argument(
        "-p",
        "--port",
        nargs=1,
        type=check_port,
        metavar="PortNum",
        dest="flask_port",
        help="the port number for the server (e.g. 8080)",
        required=True,
    )

    args = parser.parse_args()

# ----------------------
# Flask Application
# ----------------------

from sklearn.ensemble import RandomForestClassifier
import joblib as jb

model = RandomForestClassifier()
model.fit([[1, 2], [0, 3], [2, 3], [2, 4]], [0, 0, 1, 1])

jb.dump(model, "./resources/classification_model.joblib")

# Environmental variables
from dotenv import load_dotenv

load_dotenv(".env")


# Entry point for other commands to run a production WSGI server
from mlapi import create_app

app = create_app()

# Entry point for the 'run' command to run a development server
if __name__ == "__main__":
    app.run(host=args.flask_host[0], port=args.flask_port[0], debug=args.debug)


# End of MLAPI Template by vitorinojoao
