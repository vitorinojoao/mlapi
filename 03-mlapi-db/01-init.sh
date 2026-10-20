#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

read_secret() {
  local name="$1"
  local path="/run/secrets/$name"
  [[ -r "$path" ]] || {
    echo "Missing secret: $name" >&2
    exit 1
  }
  cat "$path"
}

export AUTH_DB_PASSWORD="$(read_secret auth_db_password)"
export CONFIG_DB_PASSWORD="$(read_secret config_db_password)"
export DATA_DB_PASSWORD="$(read_secret data_db_password)"

psql --username "$POSTGRES_USER" --dbname postgres \
  --set ON_ERROR_STOP=1 <<'SQL'
\getenv auth_password AUTH_DB_PASSWORD
\getenv config_password CONFIG_DB_PASSWORD
\getenv data_password DATA_DB_PASSWORD

CREATE ROLE auth_user LOGIN PASSWORD :'auth_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE config_user LOGIN PASSWORD :'config_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE data_user LOGIN PASSWORD :'data_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

CREATE DATABASE auth_db OWNER auth_user;
CREATE DATABASE config_db OWNER config_user;
CREATE DATABASE data_db OWNER data_user;

REVOKE ALL ON DATABASE auth_db FROM PUBLIC;
REVOKE ALL ON DATABASE config_db FROM PUBLIC;
REVOKE ALL ON DATABASE data_db FROM PUBLIC;

GRANT CONNECT ON DATABASE auth_db TO auth_user;
GRANT CONNECT ON DATABASE config_db TO config_user;
GRANT CONNECT ON DATABASE data_db TO data_user;

SQL

unset AUTH_DB_PASSWORD CONFIG_DB_PASSWORD DATA_DB_PASSWORD

