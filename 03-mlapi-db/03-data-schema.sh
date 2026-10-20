#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

## PSQL command to create DB_DATA_NAME schema
## Note: using postgres superuser only during initialization
psql --dbname "$DB_DATA_NAME" \
    --username postgres \
    --set ON_ERROR_STOP=1 \
    <<'EOSQL'

CREATE TABLE IF NOT EXISTS tasks_pending (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks_done (
    task_id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    done_at TIMESTAMPTZ DEFAULT NULL,
    done_success BOOL DEFAULT NULL,
    done_message TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS input_data (
    task_id UUID PRIMARY KEY,
    input_data REAL[] NOT NULL
);

CREATE TABLE IF NOT EXISTS output_results (
    task_id UUID PRIMARY KEY,
    output_results TEXT[] NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_pending_lifo ON tasks_pending (created_at DESC, task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_pending_fifo ON tasks_pending (created_at ASC, task_id);

EOSQL
