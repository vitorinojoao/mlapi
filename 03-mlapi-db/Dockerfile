FROM postgres:18-trixie

## Require DB_PORT build argument
ARG DB_PORT

## Assign the official PGPORT environmental variable
ENV PGPORT=$DB_PORT

## Copy necessary files
COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY pg_hba.conf /etc/postgresql/pg_hba.conf
COPY 01-init.sh /docker-entrypoint-initdb.d/01-init.sh
COPY 02-auth-schema.sh /docker-entrypoint-initdb.d/02-auth-schema.sh
COPY 03-data-schema.sh /docker-entrypoint-initdb.d/03-data-schema.sh

## Assign permissions
RUN chmod 0644 /etc/postgresql/postgresql.conf \
    && chmod 0644 /etc/postgresql/pg_hba.conf \
    && chmod 0755 /docker-entrypoint-initdb.d/01-init.sh \
    && chmod 0755 /docker-entrypoint-initdb.d/02-auth-schema.sh \
    && chmod 0755 /docker-entrypoint-initdb.d/03-data-schema.sh

## Execute the official CMD command
CMD ["postgres", \
    "-c", "config_file=/etc/postgresql/postgresql.conf", \
    "-c", "hba_file=/etc/postgresql/pg_hba.conf"]
