# ------------------------------------------------------------
# COMMAND-LINE INTERFACE
# ------------------------------------------------------------

if __name__ == "__main__":
    from argparse import ArgumentParser, ArgumentTypeError, RawTextHelpFormatter

    parser = ArgumentParser(
        description="Generate a signed token for a JWT authorization scheme",
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "-r",
        "--reset",
        action="store_true",
        help="whether to create a completely new private and public key pair"
        + "\n(otherwise, attempt to load from filepath in environmental variables)",
    )

    def check_days(value):
        try:
            ivalue = int(value)
            if ivalue < 0:
                raise Exception()

        except:
            raise ArgumentTypeError(
                "Invalid option for -d, --days argument."
                + " Repeat with only --help to see the valid options."
            )
        return ivalue

    requiredNamed = parser.add_argument_group("required named arguments")

    requiredNamed.add_argument(
        "-u",
        "--client",
        nargs=1,
        type=str,
        metavar="ClientID",
        dest="client_identifier",
        help="the identifier of the client for who the token will be generated",
        required=True,
    )

    requiredNamed.add_argument(
        "-d",
        "--days",
        nargs=1,
        type=check_days,
        metavar="NumDays",
        dest="access_days",
        help="the number of days the client has access before it expires"
        + "\n-d 0 : access does not expire"
        + "\n-d 1 : access for 1 day from this moment"
        + "\n-d 7 : access for 1 week from this moment"
        + "\n-d N : access for N days from this moment",
        required=True,
    )

    args = parser.parse_args()

# ------------------------------------------------------------
# REGULAR CODE
# ------------------------------------------------------------

import os
from dotenv import load_dotenv

import jwt
import time
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Environmental variables
load_dotenv(".env")


def create_jwt(reset, client_identifier, access_days):
    """
    Independent method to generate a token for a JWT authorization scheme
    with an RSA signature using a public and private key pair.
    """

    client_identifier = str(client_identifier)
    if len(client_identifier) == 0:
        raise ValueError(
            "Unsupported client identifier."
            + " Please use an adequate identifier for each client."
        )

    access_days = int(access_days)
    if access_days < 0:
        raise ValueError(
            "Unsupported number of days."
            + " Please use a positive number of days that a client has access"
            + " or 0 for access that does not expire."
        )

    secret = bytes(os.getenv("AUTH_SECRET"), encoding="utf-8")
    private_key_filepath = os.getenv("AUTH_PRIVATE_KEY_FILEPATH")
    public_key_filepath = os.getenv("AUTH_PUBLIC_KEY_FILEPATH")
    token_directory = os.getenv("AUTH_TOKEN_DIRECTORY")
    issuer = os.getenv("AUTH_ISSUER")

    algorithm = os.getenv("AUTH_ALGORITHM")
    if not algorithm.lower().startswith("rs"):
        raise ValueError(
            "Currently, only the RSA algorithm can be used for encoding/decoding tokens."
            + " Please use an algorithm like 'RS256', 'RS384', or 'RS512'."
        )

    algnum = int(algorithm[2:])
    if algnum % 256 != 0 and algnum % 384 != 0:
        raise ValueError(
            "The RSA algorithm is no longer secure with hash values lower than 256 bits."
            + " Please use an algorithm like 'RS256', 'RS384', or 'RS512'."
        )

    timestamp = int(time.time())

    if bool(reset):
        # Generate a completely new private and public key pair
        private_key = rsa.generate_private_key(
            # Should always use 65537 (can be 3 for very specific legacy purposes)
            public_exponent=65537,
            # RSA-2048 with SHA-256, RSA-3072 with SHA-384, RSA-4096 with SHA-512
            key_size=algnum * 8,
        )

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(secret),
        )

        # Save the new private key (overwriting the previous key)
        # It can be used to generate as many signed tokens as necessary
        # Do not share the private key with unauthorized personnel
        try:
            with open(private_key_filepath, "wb") as f:
                f.write(private_pem)
        except:
            raise OSError("Could not write in the specified private key file.")

        public_key = private_key.public_key()

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Save the new public key (overwriting the previous key)
        # It can be used to verify a token when a request is received
        # The public key may be shared to enable external verification
        try:
            with open(public_key_filepath, "wb") as f:
                f.write(public_pem)
        except:
            raise OSError("Could not write in the specified public key file.")

    else:
        # Load a previously generated private key to reutilize it
        try:
            with open(private_key_filepath, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(), password=secret, backend=default_backend()
                )
        except:
            raise OSError("Could not load the specified private key file.")

    # Use standard ["iss", "iat", "exp", "sub"] claims in payload
    expiration = (
        timestamp + (86400 * access_days) - 1
        if access_days > 0
        else timestamp + 3155673599
    )

    payload = {
        "iss": issuer,
        "iat": timestamp,
        "exp": expiration,
        "sub": client_identifier,
    }

    # Generate a new signed token
    token = jwt.encode(payload, private_key, algorithm=algorithm)

    # Update the token index with helpful information about the new token
    try:
        line = "token_" + str(timestamp) + ".txt\t|" + client_identifier + "\t|"

        if access_days > 0:
            line += (
                "access from "
                + datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                + " until "
                + datetime.utcfromtimestamp(expiration).strftime("%Y-%m-%d %H:%M:%S")
                + " UTC"
            )

        else:
            line += "access does not expire"

        with open(token_directory + "/token_index.txt", "a") as f:
            f.write(line + "\n")
    except:
        raise OSError("Could not write in the specified token directory.")

    # Save the new token, identified by the timestamp of its creation
    try:
        with open(token_directory + "/token_" + str(timestamp) + ".txt", "w") as f:
            f.write(token + "\n")
    except:
        raise OSError("Could not write in the specified token directory.")


# Entry point for the 'auth' command to generate a signed token
if __name__ == "__main__":
    create_jwt(args.reset, args.client_identifier[0], args.access_days[0])
