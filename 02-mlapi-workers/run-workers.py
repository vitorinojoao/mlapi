"""run-workers"""

import os
import logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "WARNING"),
    format="%(asctime)s %(levelname)s %(message)s",
)

## Entrypoint function starts worker processes/threads
from src.workers import start_workers

start_workers()
