#!/bin/sh
set -eu
mkdir -p secrets
chmod 700 secrets
umask 077
for f in postgres_admin_password auth_db_password config_db_password data_db_password flask_secret_key security_password_salt initial_admin_password redis_password; do
  if [ ! -s "secrets/$f" ]; then openssl rand -base64 36 | tr -d '\n' > "secrets/$f"; fi
  # Local Compose file-backed secrets preserve source file permissions on Linux. The parent
  # directory is private to the host owner; readable files let non-root container users read them.
  chmod 644 "secrets/$f"
done
printf 'Secrets generated. Retrieve initial_admin_password securely to sign in; do not commit secrets/.\n'
