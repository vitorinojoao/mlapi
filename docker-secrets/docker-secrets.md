## Docker Secrets in Linux

You can execute the automated shell script:

```bash
    chmod +x generate-secrets.sh && ./generate-secrets.sh
```

## Docker Secrets in Windows

You can install 'openssl' and manually generate each secret:

```bash
    openssl rand -hex 32 > cache_password
```

```bash
    openssl rand -hex 32 > db_auth_password
```

```bash
    openssl rand -hex 32 > db_data_password
```
