"""workers"""

import os
import logging
import uuid
import requests
from requests.adapters import HTTPAdapter

from psycopg.types.json import Jsonb
from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler

from .db_adapter import secret, connect


def start_workers():
    db_adapter = None
    model_wrapper = None

    url_list = [
        os.environ["APP_EXTERNAL_URL_1"].rstrip("/"),
        os.environ["APP_EXTERNAL_URL_2"].rstrip("/"),
    ]

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

    ## -----------------------------------

    ## High-frequency lightweight tasks in coalescing threads
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

    ## Lower-frequency heavyweight tasks in coalescing processes
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
        task_daily,
        id="task_daily",
        coalesce=True,
        trigger="cron",
        hour=0,
        minute=1,
        misfire_grace_time=3600,
        args=[db_adapter, url_list],
    )
    logging.warning("task_daily added to process_scheduler")

    ## -----------------------------------

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

    ## -----------------------------------


def creds(prefix):
    return secret(prefix + "_DB_USER"), secret(prefix + "_DB_PASSWORD")


def cfg():
    u, p = creds("CONFIG")
    return connect("config", u, p)


def data():
    u, p = creds("DATA")
    return connect("data", u, p)


def get_config():
    with cfg() as c, c.cursor() as cur:
        cur.execute("SELECT * FROM system_config ORDER BY config_id DESC LIMIT 1")
        return cur.fetchone()


def task_high_frequency(db_adapter, model_wrapper):
    # Claim task
    # Select data samples
    # Do task
    # Insert data results
    # Complete task
    # Log it

    conf = get_config()
    order = conf["task_order"]

    task = None
    # Claim tasks with SKIP LOCKED so that multiple workers don't process the same task
    with cfg() as c, c.cursor() as cur:
        cur.execute(
            "SELECT p.task_id,p.user_id,p.created_at FROM pending_tasks p JOIN submission_outbox o USING(task_id) WHERE p.status='pending' AND o.state='complete' ORDER BY p.created_at "
            + ("ASC" if order == "oldest" else "DESC")
            + " FOR UPDATE OF p SKIP LOCKED LIMIT 1"
        )
        task = cur.fetchone()
        if not task:
            return False
        cur.execute(
            "UPDATE pending_tasks SET status='processing' WHERE task_id=%s",
            (task["task_id"],),
        )
    try:
        with data() as c, c.cursor() as cur:
            cur.execute(
                "SELECT td.data_id, s.samples FROM task_data td JOIN samples s USING(data_id) WHERE td.task_id=%s",
                (task["task_id"],),
            )
            source = cur.fetchone()
        if not source:
            raise RuntimeError("sample_missing")
        # Replace this deterministic example transform with the actual workload
        samples = source["samples"]
        if isinstance(samples, list):
            result = {"sample_count": len(samples), "items": samples}
        else:
            result = {"sample_count": len(samples), "keys": sorted(samples.keys())}
        result_id = uuid.uuid4()
        with data() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO results(results_id,result) VALUES (%s,%s)",
                (result_id, Jsonb(result)),
            )
            cur.execute(
                "UPDATE task_data SET results_id=%s WHERE task_id=%s",
                (result_id, task["task_id"]),
            )
        with cfg() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO completed_tasks(task_id,user_id,created_at,completed_at,status) VALUES (%s,%s,%s,now(),'completed') ON CONFLICT(task_id) DO NOTHING",
                (task["task_id"], task["user_id"], task["created_at"]),
            )
            cur.execute(
                "DELETE FROM pending_tasks WHERE task_id=%s", (task["task_id"],)
            )
            cur.execute(
                "UPDATE submission_outbox SET state='processed' WHERE task_id=%s",
                (task["task_id"],),
            )
        log.info("completed task_id=%s", task["task_id"])
        return True

    except Exception:
        try:
            with cfg() as c, c.cursor() as cur:
                cur.execute(
                    "UPDATE pending_tasks SET status='failed',error_code=%s WHERE task_id=%s",
                    ("processing_error", task["task_id"]),
                )
            log.exception("task failed task_id=%s", task["task_id"])

        except Exception:
            log.exception("db failed task_id=%s", task["task_id"])

        return False


def task_low_frequency(db_adapter):
    # Select old tasks
    # Delete respective data
    # Log it

    conf = get_config()

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
    if old_pending or old_done:
        log.info(
            "cleanup removed payload for %d tasks", len(old_pending) + len(old_done)
        )


def task_daily(db_adapter, url_list):
    http = requests.Session()
    http.trust_env = False
    http.mount("https://", HTTPAdapter(max_retries=5))

    response = http.get(
        APP_EXTERNAL_URL_1 + "/status",
        timeout=(3, 10),
        allow_redirects=False,
    )
    response.raise_for_status()
    return response.json()
