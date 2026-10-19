"""workers"""

import os
import logging
import uuid
import requests
from requests.adapters import HTTPAdapter

from psycopg.types.json import Jsonb
from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler

from .db_adapter import secret, connect

from pathlib import Path


def secret(name, required=True):
    path = os.getenv(name + "_FILE")
    if path:
        try:
            value = Path(path).read_text().strip()
        except OSError:
            if required:
                raise
            return ""
    else:
        value = os.getenv(name, "").strip()
    if required and not value:
        raise RuntimeError(f"Missing required secret/config: {name}")
    return value


def start_workers():
    last_in_first_out = True

    model_filepath = None
    class_names = None

    db_adapter = DBAdapter(
        db_host,
        db_port,
        db_timeout,
        db_name,
        db_user,
        db_password,
        task_last_in_first_out,
        task_completed_time_to_live,
        task_pending_time_to_live,
    )
    model_wrapper = ModelWrapper(model_filepath, class_names)

    url_list = [
        os.environ["APP_EXTERNAL_URL_1"].rstrip("/"),
        os.environ["APP_EXTERNAL_URL_2"].rstrip("/"),
    ]

    email_list = []

    max_threads = 10
    max_tasks_per_thread = 100

    max_processes = 1
    max_tasks_per_process = 100

    ## Create the main scheduler for worker threads
    thread_scheduler = BlockingScheduler(
        executors={
            "threadpool": {
                "type": "threadpool",
                "max_workers": max_threads,
                "pool_kwargs": {"max_tasks_per_child": max_tasks_per_thread},
            },
        }
    )
    logging.warning("thread_scheduler created")

    ## Create the background scheduler for worker processes
    process_scheduler = BackgroundScheduler(
        executors={
            "processpool": {
                "type": "processpool",
                "max_workers": max_processes,
                "pool_kwargs": {"max_tasks_per_child": max_tasks_per_process},
            },
        }
    )
    logging.warning("process_scheduler created")

    ## ----------------------------------------

    ## Lightweight tasks in coalescing threads
    thread_scheduler.add_job(
        task_high_frequency,
        id="task_high_frequency",
        coalesce=True,
        trigger="interval",
        seconds=5,
        max_instances=1,
        args=[db_adapter, model_wrapper],
    )
    logging.warning("task_high_frequency added to thread_scheduler")

    ## Heavyweight tasks in coalescing processes
    process_scheduler.add_job(
        task_low_frequency,
        id="task_low_frequency",
        coalesce=True,
        trigger="interval",
        seconds=60,
        max_instances=1,
        args=[db_adapter],
    )
    logging.warning("task_low_frequency added to process_scheduler")

    ## Scheduled tasks in cron-based processes with grace time
    process_scheduler.add_job(
        task_daily_email,
        id="task_daily",
        coalesce=True,
        trigger="cron",
        hour=0,
        minute=1,
        misfire_grace_time=3600,
        args=[db_adapter, email_list],
    )
    logging.warning("task_daily_email added to process_scheduler")

    process_scheduler.add_job(
        task_daily_url,
        id="task_daily",
        coalesce=True,
        trigger="cron",
        hour=0,
        minute=5,
        misfire_grace_time=3600,
        args=[db_adapter, url_list],
    )
    logging.warning("task_daily_url added to process_scheduler")

    ## ----------------------------------------

    ## Start the background scheduler
    logging.warning("process_scheduler started")
    process_scheduler.start()

    ## Start the main scheduler
    try:
        logging.warning("thread_scheduler started")
        thread_scheduler.start()

    except KeyboardInterrupt:
        logging.warning("stopping due to keyboard interrupt")

    except SystemExit:
        logging.warning("stopping due to system exit")

    ## Stop without waiting for heavyweight tasks
    finally:
        thread_scheduler.shutdown(wait=True)
        process_scheduler.shutdown(wait=False)

    ## ----------------------------------------


def task_high_frequency(db_adapter, model_wrapper):
    try:
        ## Claim task and select data samples
        task, source = db_adapter.db_claim_task()

        if not source:
            raise RuntimeError("sample_missing")

        ## ----------------------------------------

        ## Do task

        # Replace this deterministic example transform with the actual workload
        samples = source["samples"]
        if isinstance(samples, list):
            result = {"sample_count": len(samples), "items": samples}
        else:
            result = {"sample_count": len(samples), "keys": sorted(samples.keys())}

        ## ----------------------------------------

        ## Complete task and insert results

        db_adapter.db_task_completed(task["task_id"], result)

        return True

    ## ----------------------------------------

    ## Deal with exception

    except Exception:
        try:
            db_adapter.db_task_failed(task["task_id"])

            logging.exception("failed task_id=%s", task["task_id"])

        except Exception:
            logging.exception("db failed in task_id=%s", task["task_id"])

        return False


def task_low_frequency(db_adapter):

    conf = get_config()

    ## ----------------------------------------

    ## Select old tasks

    # Metadata remains in config; only samples/results/link rows are removed from data

    with cfg() as c, c.cursor() as cur:
        if conf["pending_ttl_seconds"]:
            cur.execute(
                "SELECT task_id FROM pending_tasks WHERE created_at < now() - (%s * interval '1 second')",
                (conf["pending_ttl_seconds"],),
            )
            old_pending = [r["task_id"] for r in cur.fetchall()]
        else:
            old_pending = []
        if conf["completed_ttl_seconds"]:
            cur.execute(
                "SELECT task_id FROM completed_tasks WHERE completed_at < now() - (%s * interval '1 second')",
                (conf["completed_ttl_seconds"],),
            )
            old_done = [r["task_id"] for r in cur.fetchall()]
        else:
            old_done = []

    ## ----------------------------------------

    ## Delete respective data

    for tid in old_pending + old_done:
        with data() as c, c.cursor() as cur:
            cur.execute(
                "DELETE FROM task_data WHERE task_id=%s RETURNING data_id,results_id",
                (tid,),
            )
            links = cur.fetchall()
            for link in links:
                if link["results_id"]:
                    cur.execute(
                        "DELETE FROM results WHERE results_id=%s", (link["results_id"],)
                    )
                cur.execute("DELETE FROM samples WHERE data_id=%s", (link["data_id"],))
        # Metadata remains, status indicates that associated payload expired.
        with cfg() as c, c.cursor() as cur:
            cur.execute(
                "UPDATE pending_tasks SET status='failed',error_code='expired' WHERE task_id=%s",
                (tid,),
            )

    ## ----------------------------------------

    ## Log it

    if old_pending or old_done:
        logging.info(
            "cleanup removed payload for %d tasks", len(old_pending) + len(old_done)
        )


def task_daily_email(db_adapter, email_list):
    # Count new tasks
    # Send email
    logging.info("task_daily_email - completed")


def task_daily_url(db_adapter, url_list):
    http = requests.Session()
    http.trust_env = False
    http.mount("https://", HTTPAdapter(max_retries=5))

    response = http.get(
        url_list + "/status",
        timeout=(3, 10),
        allow_redirects=False,
    )
    response.raise_for_status()
    logging.info("task_daily_url - completed")
