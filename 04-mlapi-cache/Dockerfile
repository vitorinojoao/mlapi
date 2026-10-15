FROM redis:8-alpine

## Copy necessary files and change owner
COPY entrypoint.sh /usr/local/bin/redis-entrypoint.sh
COPY redis.conf.template /usr/local/etc/redis-templates/redis.conf.template

## Assign permissions
RUN chmod 0755 /usr/local/bin/redis-entrypoint.sh \
    && apk add --no-cache gettext

## Use custom entrypoint script for environmental variables
ENTRYPOINT ["/usr/local/bin/redis-entrypoint.sh"]

## Execute the official CMD command
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
