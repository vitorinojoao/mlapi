"""workers"""

import os
import logging
from pathlib import Path

import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler

from .db_adapter import DBAdapter
from .model_wrapper import ModelWrapper


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

    task_last_in_first_out = True
    task_pending_time_to_live = 3600
    task_done_time_to_live = 172800
    input_data_time_to_live = 1
    output_results_time_to_live = 3600

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
        task_pending_time_to_live,
        task_done_time_to_live,
        input_data_time_to_live,
        output_results_time_to_live,
    )
    model_wrapper = ModelWrapper(model_filepath, class_names)

    url_list = [
        os.environ["APP_EXTERNAL_URL_1"].rstrip("/"),
        os.environ["APP_EXTERNAL_URL_2"].rstrip("/"),
    ]

    email_list = []

    max_threads = 10
    max_tasks_per_thread = 100

    max_processes = 2
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
        task_high_frequency_prediction,
        id="task_high_frequency_prediction",
        coalesce=True,
        trigger="interval",
        seconds=5,
        max_instances=1,
        args=[db_adapter, model_wrapper],
    )
    logging.warning("task_high_frequency_prediction added to thread_scheduler")

    ## Heavyweight tasks in coalescing processes
    process_scheduler.add_job(
        task_low_frequency_cleanup,
        id="task_low_frequency_cleanup",
        coalesce=True,
        trigger="interval",
        seconds=60,
        max_instances=1,
        args=[db_adapter],
    )
    logging.warning("task_low_frequency_cleanup  added to process_scheduler")

    ## Scheduled tasks in cron-based processes with grace time
    process_scheduler.add_job(
        task_daily_summary_email,
        id="task_daily_summary_email",
        coalesce=True,
        trigger="cron",
        hour=0,
        minute=1,
        misfire_grace_time=3600,
        args=[db_adapter, email_list],
    )
    logging.warning("task_daily_summary_email added to process_scheduler")

    process_scheduler.add_job(
        task_daily_fetch_url,
        id="task_daily_fetch_url",
        coalesce=True,
        trigger="cron",
        hour=0,
        minute=5,
        misfire_grace_time=3600,
        args=[db_adapter, url_list],
    )
    logging.warning("task_daily_fetch_url added to process_scheduler")

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


def task_high_frequency_prediction(db_adapter, model_wrapper):
    try:
        claimed = db_adapter.claim_pending_task()

        if claimed:
            task_id, user_id, created_at, input_data = claimed
        else:
            return

        if input_data:
            input_data = np.array(input_data)

            n_samples = input_data.shape[0]
        else:
            raise ValueError("No input data")

        ## ----------------------------------------

        output_results = model_wrapper.predict(input_data)

        output_results = model_wrapper.postprocess_class_scores(
            output_results, n_samples
        )

        ## ----------------------------------------

        db_adapter.register_task_success(
            task_id, output_results, model_wrapper.model_name
        )

    except Exception as e:
        try:
            logging.error("prediction task_id=%s error=%s", task_id, str(e))

            db_adapter.register_task_error(task_id, str(e))

        except Exception:
            pass


## ----------------------------------------


def task_low_frequency_cleanup(db_adapter):
    try:
        db_adapter.cleanup_pending_done_tasks()

        db_adapter.cleanup_input_output()

    except Exception as e:
        logging.error("cleanup error=%s", str(e))


## ----------------------------------------


def task_daily_summary_email(db_adapter, email_list):
    try:
        count_success, count_error, count_pending = (
            db_adapter.summary_pending_done_tasks(summary_hours=24)
        )

        ## Send an email with:
        ## count_success, count_error, count_pending

        ## To each address in:
        ## email_list

    except Exception as e:
        logging.error("daily summary email error=%s", str(e))


## ----------------------------------------


def task_daily_fetch_url(db_adapter, url_list):
    import requests
    from requests.adapters import HTTPAdapter

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
