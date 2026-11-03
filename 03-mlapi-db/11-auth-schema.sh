#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

## Create DB_AUTH schema
## Note: using postgres superuser only during initialization
psql --dbname "$DB_AUTH_NAME" \
    --username postgres \
    --set ON_ERROR_STOP=1 \
    <<'EOSQL'

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,

    -- Required for Flask-Security authentication
    fs_uniquifier VARCHAR(64) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    confirmed_at TIMESTAMPTZ,

    -- Required for Flask-Security login tracking
    last_login_at TIMESTAMPTZ,
    current_login_at TIMESTAMPTZ,
    last_login_ip VARCHAR(45),
    current_login_ip VARCHAR(45),
    login_count INTEGER,

    CONSTRAINT users_login_count_nonnegative
        CHECK (login_count IS NULL OR login_count >= 0)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,

    PRIMARY KEY (user_id, role_id),

    CONSTRAINT fk_user_roles_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_user_roles_role
        FOREIGN KEY (role_id)
        REFERENCES roles(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_email
    ON users(email);

CREATE INDEX IF NOT EXISTS idx_users_fs_uniquifier
    ON users(fs_uniquifier);

CREATE INDEX IF NOT EXISTS idx_user_roles_role_id
    ON user_roles(role_id);

EOSQL
