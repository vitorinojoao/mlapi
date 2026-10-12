FROM postgres:18-trixie

## Assign the official PG_PORT build variable
ARG ARG_DB_PORT
ENV PG_PORT=$ARG_DB_PORT

## Copy necessary files
COPY 01-init.sh /docker-entrypoint-initdb.d/01-init.sh
COPY postgresql.conf /etc/postgresql/postgresql.conf

## Assign permissions
RUN chmod 0755 /docker-entrypoint-initdb.d/01-init.sh \
    && chmod 0644 /etc/postgresql/postgresql.conf

## Pass flags to the official CMD ["postgres"] command
CMD ["-c", "config_file=/etc/postgresql/postgresql.conf"]
