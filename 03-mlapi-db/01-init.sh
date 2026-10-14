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

CREATE ROLE auth_app LOGIN PASSWORD :'auth_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE config_app LOGIN PASSWORD :'config_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE data_app LOGIN PASSWORD :'data_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

CREATE DATABASE auth OWNER auth_app;
CREATE DATABASE config OWNER config_app;
CREATE DATABASE data OWNER data_app;

REVOKE ALL ON DATABASE auth FROM PUBLIC;
REVOKE ALL ON DATABASE config FROM PUBLIC;
REVOKE ALL ON DATABASE data FROM PUBLIC;

GRANT CONNECT ON DATABASE auth TO auth_app;
GRANT CONNECT ON DATABASE config TO config_app;
GRANT CONNECT ON DATABASE data TO data_app;
SQL

unset AUTH_DB_PASSWORD CONFIG_DB_PASSWORD DATA_DB_PASSWORD
