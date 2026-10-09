FROM nginx:stable-alpine

RUN apk add --no-cache openssl && mkdir -p /etc/nginx/tls

COPY entrypoint.sh /usr/local/bin/cert-entrypoint.sh
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

RUN chmod 0755 /usr/local/bin/cert-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/cert-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
