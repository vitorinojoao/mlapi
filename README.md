# Machine Learning API

A template of a secure Application Programming Interface for Machine Learning models.  
Copyright (c) 2024-2026 João Vitorino  

## Overview

To deploy ML models in a web server and securely access their predictions,  
you can use this API template and improve it to better suit your needs.  

The `app.py` is the main Python file with the creation of a Flask application,  
the initialization of several blueprints, and the setup of the default routes.  

The template is divided into three folders:

- **mlapi** - the entire Python code of the API with useful comments (e.g., blueprints and objects).
- **resources** - the resources required for the API to work properly (e.g., models and encodings).
- **files** - supplementary files to help you interact with the API (e.g., commands and requests).

![Overview](https://raw.githubusercontent.com/vitorinojoao/mlapi/main/files/overview.png)

## Sample Code

&rarr; **How to preprocess the JSON body of a request?**  
A 2D input array can be created, converting categorical features into numerical encodings.  
You can use and improve the code of `data_preprocessor.py`.  

&rarr; **How to load and use an ML model in an efficient way?**  
A model can be wrapped in a single object that is used to respond to every request.  
You can use and improve the code of `model_wrapper.py`.  

&rarr; **How to postprocess the anomaly or class predictions?**  
A 1D output array can be created, converting anomaly scores or confidence scores to labels.  
You can use and improve the code of `data_postprocessor.py`.  

&rarr; **How to send multiple requests to different routes?**  
Several GET and POST requests can be sent by each client, as long as they use valid tokens.  
You can see the possible requests in `mlapirequests.json`.  

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

Validate configuration
docker compose config --quiet

Build all three images
docker compose build

Start services in the background
docker compose up -d

Check status and health
docker compose ps

Inspect logs
docker compose logs --tail=100 nginx api db

## Local DNS Configuration

1: Point api.home.arpa to the Docker host's IP address in your local DNS server or the hosts file on your client

2: Export the public CA certificate for installation on client devices
docker compose cp nginx:/etc/nginx/tls/local-ca.crt ./local-ca.crt

3: Install local-ca.crt into the client's trusted root certificate store. Never distribute local-ca.key

4: Test HTTPS
curl --fail --show-error https://api.home.arpa/health

5: If DNS is not yet configured, test using the host IP while explicitly setting the hostname
curl --resolve api.home.arpa:443:127.0.0.1 https://api.home.arpa/health

Replace 127.0.0.1 with the correct host IP when testing from another machine
Do not use curl -k as a permanent workaround for certificate errors
