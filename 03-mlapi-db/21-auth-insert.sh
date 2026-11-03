#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

## Insert initial seed data into DB_AUTH
## Note: using postgres superuser only during initialization
psql --dbname "$DB_AUTH_NAME" \
    --username postgres \
    --set ON_ERROR_STOP=1 \
    <<'EOSQL'

BEGIN;

INSERT INTO roles
    (name, description)
VALUES
    ('provider',    'Role to post tasks'),
    ('consumer',    'Role to get task results'),
    ('prosumer',    'Role to post and get tasks'),
    ('privileged',  'Role to access task audit information'),
    ('admin',       'Role to manage configuration and users')
ON CONFLICT (name) DO NOTHING;

COMMIT;

EOSQL
