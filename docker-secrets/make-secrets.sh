#!/bin/sh
set -Eeuo pipefail
umask 077

chmod 700 .

for f in cache_password db_auth_password db_data_password flask_secret_key security_password_salt; do
  if [ ! -s "./$f" ]; then openssl rand -base64 36 | tr -d '\n' > "./$f"; fi
  # Local Compose file-backed secrets preserve source file permissions on Linux. The parent
  # directory is private to the host owner; readable files let non-root container users read them.
  chmod 644 "./$f"
done
printf 'Secrets generated\n'
