# Machine Learning API

A template of a secure and scalable API for Machine Learning models.  
Copyright (c) 2024-2026 João Vitorino  

## Overview

To deploy one or more ML models in a backend production server,  
following cyber security best-practices and software design principles,  
you can start from this template and modify it to better suit your needs.  

The template is divided into multiple parts:  

- **docker-compose.yml** &nbsp;&ndash;&nbsp; Configuration of Docker services, networks, and volumes.
- **01-mlapi-app** &nbsp;&ndash;&nbsp; Flask web app with Gunicorn WSGI &nbsp;&ndash;&nbsp; for REST API routes and light tasks.
- **02-mlapi-workers** &nbsp;&ndash;&nbsp; Python worker processes/threads with APScheduler &nbsp;&ndash;&nbsp; for heavy tasks.
- **03-mlapi-db** &nbsp;&ndash;&nbsp; PostgreSQL primary relational database &nbsp;&ndash;&nbsp; for auth and data schemas.
- **04-mlapi-cache** &nbsp;&ndash;&nbsp; Redis distributed in-memory cache &nbsp;&ndash;&nbsp; to improve efficiency.
- **05-mlapi-proxy** &nbsp;&ndash;&nbsp; Nginx SSL/TLS reverse proxy with rate limiting &nbsp;&ndash;&nbsp; to improve security.

## Architecture

```mermaid
architecture-beta
    group edge_net(cloud)[Edge Network]
    group isolated_net(cloud)[Isolated Network]

    service inbound(internet)[IN]
    service outbound(internet)[OUT]

    service proxy(server)[Proxy] in edge_net
    service app(server)[Web App] in edge_net
    service workers(server)[Workers] in edge_net

    service cache(database)[Cache] in isolated_net
    service db(database)[Database] in isolated_net

    service models(disk)[(models)] in edge_net
    service volume(disk)[(persistence)] in isolated_net

    inbound:R --> L:proxy
    proxy:R --> L:app
    app:R --> L:cache
    app:R --> L:db
    app:B --> T:models

    outbound:R <-- L:workers
    workers:T --> B:models
    workers:R --> L:db
    db:B --> T:volume

    align row inbound proxy app cache
    align row models db
    align row outbound workers volume

    align column inbound outbound
    align column app models workers
    align column cache db volume
```

## Docker Commands

- Generate secret files

```bash
    chmod +x ./docker-secrets/generate-secrets.sh && ./docker-secrets/generate-secrets.sh
```

- Validate configuration

```bash
    docker compose config --quiet
```

- Build all images

```bash
    docker compose build app-service workers-service db-service cache-service proxy-service
```

- Start all services/networks in the background

```bash
    docker compose up -d app-service workers-service db-service cache-service proxy-service
```

- Check status and health

```bash
    docker compose ps
```

- Check most recent logs

```bash
    docker compose logs --tail=100 app-service workers-service db-service cache-service proxy-service
```

- Stop all services/networks, without affecting persistent volumes

```bash
    docker compose down app-service workers-service db-service cache-service proxy-service
```

- Permanently delete all images and persistent volumes

```bash
    docker system prune -a --volumes
```

## Local DNS Commands

- Point mlapi.home.arpa to the Docker host's IP address in your local DNS server or the hosts file on your client

- Export the public CA certificate for installation on client devices

```bash
    docker compose cp nginx:/etc/nginx/tls/local-ca.crt ./local-ca.crt
```

- Install local-ca.crt into the client's trusted root certificate store. Never distribute local-ca.key

- Test HTTPS

```bash
    curl --fail --show-error https://mlapi.home.arpa/health
```

- If DNS is not yet configured, test using the host IP while explicitly setting the hostname. Never use curl -k as a workaround

```bash
    curl --resolve mlapi.home.arpa:443:127.0.0.1 https://mlapi.home.arpa/health
```
