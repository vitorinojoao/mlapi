#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

## Function to read a secret file and assign it to a local variable
## Usage: read_secret <local_var> <filepath_var>
read_secret() {
    local local_var="$1"
    local filepath_var="$2"

    if [[ ! -r "$filepath_var" ]]; then
        echo "Missing or unreadable secret file at $filepath_var" >&2
        exit 1
    fi

    printf -v "$local_var" '%s' "$(<"$filepath_var")"
}

read_secret db_auth_password "$DB_AUTH_PASSWORD_FILE"
read_secret db_data_password "$DB_DATA_PASSWORD_FILE"

## PSQL command to initialize with local variables
## Note: double quotes for identifiers (:"db_name"), single quotes for literals (:'db_password')
psql --dbname postgres \
    --username postgres \
    --variable db_auth_name="$DB_AUTH_NAME" \
    --variable db_auth_user="$DB_AUTH_USER" \
    --variable db_auth_password="$db_auth_password" \
    --variable db_data_name="$DB_DATA_NAME" \
    --variable db_data_user="$DB_DATA_USER" \
    --variable db_data_password="$db_data_password" \
    --set ON_ERROR_STOP=1 \
    <<'EOSQL'

CREATE ROLE :"db_auth_user" LOGIN PASSWORD :'db_auth_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE :"db_data_user" LOGIN PASSWORD :'db_data_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

CREATE DATABASE :"db_auth_name" OWNER :"db_auth_user";
CREATE DATABASE :"db_data_name" OWNER :"db_data_user";

REVOKE ALL ON DATABASE :"db_auth_name" FROM PUBLIC;
REVOKE ALL ON DATABASE :"db_data_name" FROM PUBLIC;

GRANT CONNECT ON DATABASE :"db_auth_name" TO :"db_auth_user";
GRANT CONNECT ON DATABASE :"db_data_name" TO :"db_data_user";

EOSQL
