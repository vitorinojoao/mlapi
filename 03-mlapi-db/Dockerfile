FROM postgres:18-trixie

## Copy necessary files
COPY 01-init.sh /docker-entrypoint-initdb.d/01-init.sh
COPY 02-schema.sh /docker-entrypoint-initdb.d/02-schema.sh
COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY pg_hba.conf /etc/postgresql/pg_hba.conf

## Assign permissions
RUN chmod 0755 /docker-entrypoint-initdb.d/01-init.sh \
    && chmod 0755 /docker-entrypoint-initdb.d/02-schema.sh \
    && chmod 0644 /etc/postgresql/postgresql.conf \
    && chmod 0644 /etc/postgresql/pg_hba.conf

## Execute the official CMD command
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf", \ 
    "-c", "hba_file=/etc/postgresql/pg_hba.conf"]
