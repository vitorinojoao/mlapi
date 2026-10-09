#!/bin/sh
set -eu
umask 077

: "${DOMAIN:?DOMAIN is required}"

# Accept a simple DNS hostname, not arbitrary OpenSSL or Nginx syntax.
if ! printf '%s' "$DOMAIN" |
  grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$'; then
  echo "Invalid DOMAIN" >&2
  exit 1
fi

TLS=/etc/nginx/tls
CA_KEY="$TLS/local-ca.key"
CA_CERT="$TLS/local-ca.crt"
SERVER_KEY="$TLS/server.key"
SERVER_CERT="$TLS/server.crt"

mkdir -p "$TLS"
chmod 700 "$TLS"

# Never silently replace an existing trust anchor if only one CA file remains.
if { [ -e "$CA_KEY" ] && [ ! -s "$CA_CERT" ]; } ||
   { [ -e "$CA_CERT" ] && [ ! -s "$CA_KEY" ]; }; then
  echo "Incomplete CA state; refusing automatic CA replacement" >&2
  exit 1
fi

if [ ! -s "$CA_KEY" ]; then
  openssl genrsa -out "$CA_KEY" 4096
  openssl req -x509 -new -sha256 -days 3650 \
    -key "$CA_KEY" \
    -out "$CA_CERT" \
    -subj "/CN=Secure Stack Local CA" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"
fi

chmod 600 "$CA_KEY"
chmod 644 "$CA_CERT"

# Rotate the leaf certificate on startup if missing or expiring soon.
RENEW=0
if [ ! -s "$SERVER_KEY" ] || [ ! -s "$SERVER_CERT" ]; then
  RENEW=1
elif ! openssl x509 -in "$SERVER_CERT" -noout -checkend 2592000; then
  RENEW=1
fi

if [ "$RENEW" = 1 ]; then
  rm -f "$SERVER_KEY" "$SERVER_CERT" "$TLS/server.csr" \
    "$TLS/server.ext" "$TLS/ca.srl"

  openssl genrsa -out "$SERVER_KEY" 3072
  openssl req -new -sha256 \
    -key "$SERVER_KEY" \
    -out "$TLS/server.csr" \
    -subj "/CN=$DOMAIN"

  printf '%s\n' \
    'basicConstraints=critical,CA:FALSE' \
    'keyUsage=critical,digitalSignature,keyEncipherment' \
    'extendedKeyUsage=serverAuth' \
    "subjectAltName=DNS:$DOMAIN" \
    > "$TLS/server.ext"

  openssl x509 -req -sha256 -days 365 \
    -in "$TLS/server.csr" \
    -CA "$CA_CERT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -out "$SERVER_CERT" \
    -extfile "$TLS/server.ext"

  rm -f "$TLS/server.csr" "$TLS/server.ext" "$TLS/ca.srl"
fi

chmod 600 "$SERVER_KEY"
chmod 644 "$SERVER_CERT"

openssl verify -CAfile "$CA_CERT" "$SERVER_CERT"
openssl x509 -in "$SERVER_CERT" -noout -checkhost "$DOMAIN"
openssl x509 -in "$SERVER_CERT" -noout -checkend 86400

envsubst '${DOMAIN}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

nginx -t

exec "$@"
