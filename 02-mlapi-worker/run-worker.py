"""run-worker"""

import os
import logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "WARNING"),
    format="%(asctime)s %(levelname)s %(message)s",
)

## Entrypoint function starts APScheduler worker(s)
from .src.worker import create_worker

create_worker()
