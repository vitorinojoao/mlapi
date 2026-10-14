#!/bin/sh
set -eu
umask 077

: "${ARG_REDIS_PORT:?ARG_REDIS_PORT is required}"
: "${ARG_REDIS_PASSWORD_FILE:?ARG_REDIS_PASSWORD_FILE is required}"

if [ ! -r "${ARG_REDIS_PASSWORD_FILE}" ]; then
    echo "Redis password secret is missing or unreadable" >&2
    exit 1
fi

ARG_REDIS_PASSWORD="$(cat "${ARG_REDIS_PASSWORD_FILE}")"

if [ -z "$ARG_REDIS_PASSWORD" ] || printf '%s' "$ARG_REDIS_PASSWORD" | grep -q '[[:space:]]'; then
    echo "Redis password must be non-empty and contain no whitespace" >&2
    exit 1
fi

envsubst '${ARG_REDIS_PORT},${ARG_REDIS_PASSWORD}' \
  < /usr/local/etc/redis/redis.conf.template \
  > /usr/local/etc/redis/redis.conf

exec /usr/local/bin/docker-entrypoint.sh "$@"
