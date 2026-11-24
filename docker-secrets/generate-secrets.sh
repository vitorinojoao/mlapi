#!/usr/bin/env bash
set -euo pipefail
umask 077

## Manually defined list of secret files
SECRETS=(
    "cache_password"
    "db_auth_password"
    "db_data_password"
)

echo -e "\nChecking secret files...\n"
chmod 700 .

for secret in "${SECRETS[@]}"; do
    ## Check if the file is missing or empty
    if [ ! -s "./$secret" ]; then
        ## Generate 32 bytes (256-bit) hex string without a trailing newline
        openssl rand -hex 32 | tr -d '\n' > "./$secret"
        echo "  - Generated new file $secret"
    else
        echo "  - Skipped existing file $secret"
    fi
done

echo -e "\nFinished successfully\n"
