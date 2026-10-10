FROM postgres:18-trixie

COPY 01-init.sh /docker-entrypoint-initdb.d/01-init.sh
COPY postgresql.conf /etc/postgresql/postgresql.conf

RUN chmod 0755 /docker-entrypoint-initdb.d/01-init.sh \
    && chmod 0644 /etc/postgresql/postgresql.conf

CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
