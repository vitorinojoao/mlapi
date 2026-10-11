## Setup docker-secrets

chmod 700 .

umask 077

openssl rand -hex 32 > postgres_admin_password
openssl rand -hex 32 > auth_db_password
openssl rand -hex 32 > config_db_password
openssl rand -hex 32 > data_db_password
