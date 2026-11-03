#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

## Insert initial seed data into DB_DATA
## Note: using postgres superuser only during initialization
psql --dbname "$DB_DATA_NAME" \
    --username postgres \
    --set ON_ERROR_STOP=1 \
    <<'EOSQL'

BEGIN;

INSERT INTO tasks_done
    (task_id, user_id, created_at, claimed_at, done_at, done_success, done_message)
VALUES
    ('11111111-1111-4111-a111-111111111111', 'admin', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, TRUE, 'init'),
ON CONFLICT (task_id) DO NOTHING;

COMMIT;

EOSQL
