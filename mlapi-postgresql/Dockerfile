FROM postgres:18-trixie

COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY init/01-init.sh /docker-entrypoint-initdb.d/01-init.sh

RUN chmod 0644 /etc/postgresql/postgresql.conf \
    && chmod 0755 /docker-entrypoint-initdb.d/01-init.sh

CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
