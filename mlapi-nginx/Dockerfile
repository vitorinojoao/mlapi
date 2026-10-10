FROM nginx:stable-alpine

COPY entrypoint.sh /usr/local/bin/nginx-entrypoint.sh
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

RUN chmod 0755 /usr/local/bin/nginx-entrypoint.sh \
    && mkdir -p /etc/nginx/tls \
    && apk add --no-cache openssl

ENTRYPOINT ["/usr/local/bin/nginx-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
