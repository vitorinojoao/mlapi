#!/bin/sh
set -eu
umask 077

: "${CACHE_PORT:?CACHE_PORT is required}"
: "${CACHE_PASSWORD_FILE:?CACHE_PASSWORD_FILE is required}"

if [ ! -r "${CACHE_PASSWORD_FILE}" ]; then
    echo "Redis cache password secret is missing or unreadable" >&2
    exit 1
fi

cache_password="$(cat "${CACHE_PASSWORD_FILE}" | tr -d '\r\n')"

if [ -z "$cache_password" ] || printf '%s' "$cache_password" | grep -q '[[:space:]]'; then
    echo "Redis cache password must be non-empty and contain no whitespace" >&2
    exit 1
fi

cache_password="$cache_password" \
envsubst '${CACHE_PORT},${cache_password}' \
  < /usr/local/etc/redis-templates/redis.conf.template \
  > /usr/local/etc/redis/redis.conf

exec /usr/local/bin/docker-entrypoint.sh "$@"
