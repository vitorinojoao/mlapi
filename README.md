# Machine Learning API

A template of a secure and scalable API for Machine Learning models.  
Copyright (c) 2024-2026 João Vitorino  

## Overview

To deploy one or more ML models in a backend web server  
and use a REST API to POST input data and GET output results,  
you can start from this template and modify it to suit your needs.  

The template is divided into multiple parts:  

- **docker-compose.yml** &nbsp;&ndash;&nbsp; The main configuration for Docker services, networks and volumes.
- **01-mlapi-app** &nbsp;&ndash;&nbsp; Python Flask app with Gunicorn WSGI &nbsp;&ndash;&nbsp; provides default blueprints and routes.
- **02-mlapi-workers** &nbsp;&ndash;&nbsp; Python worker processes/threads with APScheduler &nbsp;&ndash;&nbsp; provides default ML tasks.
- **03-mlapi-db** &nbsp;&ndash;&nbsp; PostgreSQL primary relational database &nbsp;&ndash;&nbsp; provides default auth and data schemas.
- **04-mlapi-cache** &nbsp;&ndash;&nbsp; Redis distributed in-memory cache &nbsp;&ndash;&nbsp; provides an efficient cache.
- **05-mlapi-proxy** &nbsp;&ndash;&nbsp; Nginx SSL/TLS reverse proxy with rate limiting &nbsp;&ndash;&nbsp; provides a secure proxy.

## Docker Secrets

mkdir -p secrets

chmod 700 secrets

umask 077

openssl rand -hex 32 > secrets/postgres_admin_password

openssl rand -hex 32 > secrets/auth_db_password

openssl rand -hex 32 > secrets/config_db_password

openssl rand -hex 32 > secrets/data_db_password

chmod 600 secrets/*

## Docker Commands

1: Validate configuration

docker compose config --quiet

2: Build all three images

docker compose build

3: Start services in the background

docker compose up -d

4: Check status and health

docker compose ps

5: Inspect logs

docker compose logs --tail=100 app-service worker-service db-service cache-service proxy-service

Stop every service:

docker compose down

Delete everything:

docker system prune -a --volumes

## Local DNS Configuration

1: Point mlapi.home.arpa to the Docker host's IP address in your local DNS server or the hosts file on your client

2: Export the public CA certificate for installation on client devices

docker compose cp nginx:/etc/nginx/tls/local-ca.crt ./local-ca.crt

3: Install local-ca.crt into the client's trusted root certificate store. Never distribute local-ca.key

4: Test HTTPS

curl --fail --show-error https://mlapi.home.arpa/health

5: If DNS is not yet configured, test using the host IP while explicitly setting the hostname

curl --resolve mlapi.home.arpa:443:127.0.0.1 https://mlapi.home.arpa/health

Replace 127.0.0.1 with the correct host IP when testing from another machine

Do not use curl -k as a permanent workaround for certificate errors
