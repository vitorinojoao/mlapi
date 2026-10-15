"""run-app"""

import os
import logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "WARNING"),
    format="%(asctime)s %(levelname)s %(message)s",
)

## Entrypoint variable 'app' is used by Gunicorn WSGI in 'run-app:app'
from .src.app import create_app

app = create_app()
