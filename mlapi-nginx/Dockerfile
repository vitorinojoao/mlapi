FROM nginx:stable-alpine

## Copy necessary files
COPY entrypoint.sh /usr/local/bin/nginx-entrypoint.sh
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

## Assign permissions, create directory, and install openssl
RUN chmod 0755 /usr/local/bin/nginx-entrypoint.sh \
    && mkdir -p /etc/nginx/tls \
    && apk add --no-cache openssl

## Use custom entrypoint script for startup certificate rotation
ENTRYPOINT ["/usr/local/bin/nginx-entrypoint.sh"]

## Execute the official CMD command
CMD ["nginx", "-g", "daemon off;"]
