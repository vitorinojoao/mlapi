#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

## PSQL command to create DB_AUTH_NAME schema
## Note: using postgres superuser only during initialization
psql --dbname "$DB_AUTH_NAME" \
    --username postgres \
    --set ON_ERROR_STOP=1 \
    <<'EOSQL'

CREATE TABLE IF NOT EXISTS auth_users (
    user_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_enabled BOOL NOT NULL DEFAULT TRUE
);

EOSQL
