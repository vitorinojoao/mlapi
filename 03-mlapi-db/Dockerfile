FROM postgres:18-trixie

## Copy necessary files
COPY 01-init.sh /docker-entrypoint-initdb.d/01-init.sh
COPY postgresql.conf /etc/postgresql/postgresql.conf

## Assign permissions
RUN chmod 0755 /docker-entrypoint-initdb.d/01-init.sh \
    && chmod 0644 /etc/postgresql/postgresql.conf

## Execute the official CMD command
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
