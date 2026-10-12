# MLAPI Template by vitorinojoao

import time
import logging
import threading
from flask import Blueprint, current_app, request, jsonify


def create_auth(
    app,
    name_route,
    logging_level,
    clients_registration,
    clients_reset_only_once,
    issuer="AS",
    algorithm="RS512",
    access_ttl_mins=70,
    refresh_ttl_mins=1500,
    public_key_save_filepath=None,
    private_key_save_filepath=None,
    private_key_save_secret=None,
):
    # ----------------------------
    # Load AUTH configuration
    # ----------------------------

    name_route = str(name_route).lower()
    bluep = Blueprint(name_route, __name__, url_prefix=f"/{name_route}")

    # Keys for a JWT authorization scheme:
    # Private key can be used to generate new signed tokens to give temporary access to clients
    # Public key can be used to verify a signed token when a client request is received
    public_key, private_key = setup_key_pair(
        algorithm,
        public_key_save_filepath,
        private_key_save_filepath,
        private_key_save_secret,
    )

    # Logging levels:
    # 0 - Disabled
    # 10 - Debug
    # 20 - Info
    # 30 - Warning
    # 40 - Error
    # 50 - Critical
    logging_level = int(logging_level) if int(logging_level) > 0 else 100

    app.config["AUTH_CONFIG"] = {
        "NAME_ROUTE": name_route,
        "LOGGING_LEVEL": logging_level,
        # -----
        "CLIENTS_REGISTRATION": {
            str(u).strip(): str(p).strip() for u, p in clients_registration.items()
        },
        "CLIENTS_RESET_ONLY_ONCE": bool(clients_reset_only_once),
        "ALLOWED_CLIENTS": {},
        "ALLOWED_LOCK": threading.Lock(),
        # -----
        "ISSUER": str(issuer),
        "ALGORITHM": str(algorithm),
        "ACCESS_TTL": 60 * int(access_ttl_mins),
        "REFRESH_TTL": 60 * int(refresh_ttl_mins),
        "ACCESS_AUD": "access",
        "REFRESH_AUD": "refresh",
        # -----
        "PUBLIC_KEY": public_key,
        "PRIVATE_KEY": private_key,
    }

    # -----------------------
    # Define AUTH routes
    # -----------------------

    @bluep.route("/", methods=["GET", "HEAD"])
    def route_auth():
        if request.method == "HEAD":
            return "", 200

        name_route = current_app.config["AUTH_CONFIG"]["NAME_ROUTE"]
        return (
            "<h1>Health Check</h1>"
            + f"<p>Resources of '{name_route}' are up and running.</p>",
            200,
        )

    @bluep.route("/refresh/", methods=["GET"])
    def route_auth_refresh():
        conf = current_app.config["AUTH_CONFIG"]
        private_key = conf["PRIVATE_KEY"]
        algorithm = conf["ALGORITHM"]

        # Validate Authorization header
        # (requires a signed refresh token)
        try:
            payload = validate_jwt(
                request.headers.get("Authorization"),
                conf["PUBLIC_KEY"],
                algorithm,
                conf["ISSUER"],
                conf["REFRESH_AUD"],
                conf["ALLOWED_CLIENTS"],
            )

        except Exception:
            return (
                "<h1>401 Unauthorized</h1>"
                + "<p>You are not authorized to access this resource.</p>",
                401,
            )

        client = payload["sub"]
        timestamp = int(time.time())

        # Perform Refresh Token Rotation
        # (requires a client to use its latest refresh token)
        with conf["ALLOWED_LOCK"]:
            allowed_clients = conf["ALLOWED_CLIENTS"]

            # Safety check for token replay
            # (to prevent misuse of previous tokens)
            if (
                client not in allowed_clients
                or allowed_clients[client] != payload["iat"]
            ):
                if client in allowed_clients:
                    # Immediately block this client instance
                    allowed_clients.pop(client)

                    if conf["LOGGING_LEVEL"] < 31:
                        logging.warning(
                            "AUTH REFRESH: Failed by %s and token replay was blocked",
                            client,
                        )

                elif conf["LOGGING_LEVEL"] < 21:
                    logging.info(
                        "AUTH REFRESH: Failed by %s but token replay was already blocked",
                        client,
                    )

                return (
                    "<h1>401 Unauthorized</h1>"
                    + "<p>You are not authorized to access this resource.</p>",
                    401,
                )

            # Allow the new token of this client instance
            # (by updating timestamp/id of latest refresh token)
            allowed_clients[client] = timestamp

        if conf["LOGGING_LEVEL"] < 21:
            logging.info("AUTH REFRESH: Successful by %s", client)

        # Generate the new refresh token
        refresh_token = generate_jwt(
            {
                "iss": conf["ISSUER"],
                "aud": conf["REFRESH_AUD"],
                "sub": client,
                "iat": timestamp,
                "exp": timestamp + conf["REFRESH_TTL"],
            },
            private_key,
            algorithm,
        )

        # Generate a temporary access token
        access_token = generate_jwt(
            {
                "iss": conf["ISSUER"],
                "aud": conf["ACCESS_AUD"],
                "sub": client,
                "iat": timestamp,
                "exp": timestamp + conf["ACCESS_TTL"],
            },
            private_key,
            algorithm,
        )

        return (
            jsonify((access_token, refresh_token)),
            200,
        )

    @bluep.route("/reset/", methods=["POST"])
    def route_auth_reset():
        conf = current_app.config["AUTH_CONFIG"]

        # Validate client registration
        # (requires a client to use its secret credentials)
        regclient = str(request.form.get("username"))
        password = str(request.form.get("password"))

        registered_clients = conf["CLIENTS_REGISTRATION"]

        if (
            regclient not in registered_clients
            or registered_clients[regclient] != password
        ):

            if regclient in registered_clients:
                if conf["LOGGING_LEVEL"] < 31:
                    logging.warning(
                        "AUTH RESET: Failed by %s with incorrect password", regclient
                    )

            elif conf["LOGGING_LEVEL"] < 21:
                logging.info("AUTH RESET: Failed by unknown client")

            return (
                "<h1>401 Unauthorized</h1>"
                + "<p>You are not authorized to access this resource.</p>",
                401,
            )

        elif conf["LOGGING_LEVEL"] < 51:
            logging.critical("AUTH RESET: Successful by %s", regclient)

        timestamp = int(time.time())
        client = regclient + str(int(timestamp))

        # Perform Client Instance Reset
        # (ensures that a trusted client can get new refresh tokens)
        with conf["ALLOWED_LOCK"]:
            allowed_clients = conf["ALLOWED_CLIENTS"]

            # Block previous client instance
            # (to prevent misuse of previous tokens)
            for c in list(allowed_clients.keys()):
                if c.startswith(regclient):
                    allowed_clients.pop(c)
                    break

            # Allow the new client instance
            # (by adding or updating timestamp/id of latest refresh token)
            allowed_clients[client] = timestamp

            # If specified, disable future resets for this client
            if conf["CLIENTS_RESET_ONLY_ONCE"]:
                registered_clients.pop(regclient)

        # Generate the new refresh token
        refresh_token = generate_jwt(
            {
                "iss": conf["ISSUER"],
                "aud": conf["REFRESH_AUD"],
                "sub": client,
                "iat": timestamp,
                "exp": timestamp + conf["REFRESH_TTL"],
            },
            conf["PRIVATE_KEY"],
            conf["ALGORITHM"],
        )

        return (
            jsonify((refresh_token,)),
            200,
        )

    # ---------------------------------
    # Define special AUTH function
    # ---------------------------------

    def auth_function(request):
        conf = current_app.config["AUTH_CONFIG"]

        # Validate Authorization header
        # (requires a signed access token)
        payload = validate_jwt(
            request.headers.get("Authorization"),
            conf["PUBLIC_KEY"],
            conf["ALGORITHM"],
            conf["ISSUER"],
            conf["ACCESS_AUD"],
            conf["ALLOWED_CLIENTS"],
        )

        return payload["sub"]

    return bluep, auth_function


def setup_key_pair(
    algorithm,
    public_key_save_filepath=None,
    private_key_save_filepath=None,
    private_key_save_secret=None,
):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    algorithm = str(algorithm)

    # Obtain the algorithm name
    if not algorithm.lower().startswith("rs"):
        raise ValueError(
            "Only the RSA algorithm is currently supported for generating signed tokens."
            + " Please use an algorithm like 'RS256', 'RS384', or 'RS512'."
        )

    # Obtain the number of bits
    nbits = int(algorithm[2:])
    if nbits % 256 != 0 and nbits % 384 != 0:
        raise ValueError(
            "The RSA algorithm is no longer secure with hash values lower than 256 bits."
            + " Please use an algorithm like 'RS256', 'RS384', or 'RS512'."
        )

    # Generate the private key
    # It can be used to generate new tokens with RSA signatures
    private_key = rsa.generate_private_key(
        # Should always use 65537 (can be 3 for specific legacy purposes)
        public_exponent=65537,
        # RSA-2048 with SHA-256, RSA-3072 with SHA-384, RSA-4096 with SHA-512
        key_size=nbits * 8,
    )

    # Generate the public key
    # It can be used to verify the RSA signature of a token
    public_key = private_key.public_key()

    # Optionally save the private key in a PEM file
    # Never share the private key nor the secret string used for its keyfile encryption
    if private_key_save_filepath is not None:

        if private_key_save_secret is None:
            raise ValueError(
                "The private key PEM file must be encrypted with a secret string."
                + " Please provide a secret string for keyfile encryption."
            )

        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                private_key_save_secret
            ),
        )

        try:
            with open(private_key_save_filepath, "wb") as f:
                f.write(private_key_pem)
        except Exception as e:
            raise ValueError(
                "Could not save the private key PEM file in the specified filepath."
            ) from e

    # Optionally save the public key in a PEM file
    # The public key may be shared to enable external verification
    if public_key_save_filepath is not None:

        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        try:
            with open(public_key_save_filepath, "wb") as f:
                f.write(public_key_pem)
        except Exception as e:
            raise ValueError(
                "Could not save the public key PEM file in the specified filepath."
            ) from e

    return public_key, private_key


def generate_jwt(payload, private_key, algorithm):
    import jwt

    # Encode JWT payload with private key
    return "Bearer " + jwt.encode(payload, private_key, algorithm=algorithm)


def validate_jwt(token, public_key, algorithm, issuer, audience, allowed_clients):
    import jwt

    try:
        # Remove Bearer keyword
        if not token.startswith("Bearer "):
            # raise jwt.exceptions.InvalidTokenError("Invalid token type.")
            raise Exception()

        token = token[7:]

        # Verify JWT header
        header = jwt.get_unverified_header(token)
        if header["typ"] != "JWT" or header["alg"] != algorithm:
            # raise jwt.exceptions.InvalidTokenError("Invalid token header.")
            raise Exception()

        # Verify and decode JWT payload with public key
        payload = jwt.decode(
            token,
            public_key,
            issuer=issuer,
            audience=audience,
            algorithms=[algorithm],
            options={"require": ("iss", "aud", "sub", "iat", "exp")},
        )

        # Verify that JWT subject is an allowed client
        if payload["sub"] not in allowed_clients:
            # raise jwt.exceptions.InvalidTokenError("Invalid token payload.")
            raise Exception()

        # Return JWT payload
        return payload

    except Exception as e:
        raise Exception("Unauthorized")


# End of MLAPI Template by vitorinojoao
