"""workers"""

import os
import logging
from pathlib import Path

import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler

from src.db_adapter import DBAdapter
from src.model_wrapper import ModelWrapper


def start_workers():
    email_list = read_env_list("WRKR_SEND_EMAIL_LIST")
    url_list = read_env_list("WRKR_FETCH_URL_LIST")

    ## ----------------------------------------

    ## Create an adapter for the database
    db_password = read_secret("DB_DATA_PASSWORD_FILE")

    db_adapter = DBAdapter(
        db_host=os.getenv("DB_HOST"),
        db_port=os.getenv("DB_PORT"),
        db_timeout=os.getenv("DB_TIMEOUT"),
        db_name=os.getenv("DB_DATA_NAME"),
        db_user=os.getenv("DB_DATA_USER"),
        db_password=db_password,
        tasks_order_last_in_first_out=os.getenv(
            "WRKR_TASKS_ORDER_LAST_IN_FIRST_OUT", "t"
        )
        .lower()
        .startswith("t"),
        tasks_summary_hours=os.getenv("WRKR_TASKS_SUMMARY_HOURS"),
        tasks_pending_time_to_live=os.getenv("WRKR_TASKS_PENDING_TIME_TO_LIVE"),
        tasks_done_time_to_live=os.getenv("WRKR_TASKS_DONE_TIME_TO_LIVE"),
        input_data_time_to_live=os.getenv("WRKR_INPUT_DATA_TIME_TO_LIVE"),
        output_results_time_to_live=os.getenv("WRKR_OUTPUT_RESULTS_TIME_TO_LIVE"),
    )
    logging.warning("db_adapter created")

    ## Create a wrapper for the ML model
    model_wrapper = ModelWrapper(
        model_filepath=os.getenv("WRKR_MODEL_FILE"),
        class_names=read_env_list("WRKR_MODEL_CLASS_NAMES_LIST"),
    )
    logging.warning("model_wrapper created")

    ## ----------------------------------------

    ## Create the main scheduler for worker threads
    thread_scheduler = BlockingScheduler(
        executors={
            "threadpool": {
                "type": "threadpool",
                "max_workers": int(os.getenv("WRKR_SCHEDULER_MAX_THREADS", "1")),
            },
        }
    )
    logging.warning("thread_scheduler created")

    ## Create the background scheduler for worker processes
    process_scheduler = BackgroundScheduler(
        executors={
            "processpool": {
                "type": "processpool",
                "max_workers": int(os.getenv("WRKR_SCHEDULER_MAX_PROCESSES", "1")),
                "pool_kwargs": {
                    "max_tasks_per_child": int(
                        os.getenv("WRKR_SCHEDULER_RESPAWN_PROCESSES", "100")
                    )
                },
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


def read_secret(filepath_var):
    ## Function to read a secret file and return a local variable

    res = None
    try:
        path = Path(os.getenv(filepath_var))
        with open(path, "r") as f:
            res = f.read().strip()

    except Exception as e:
        raise RuntimeError(
            f"Missing or unreadable secret file at {filepath_var}"
        ) from e

    if res:
        return res
    else:
        raise RuntimeError(f"Empty file without a secret at {filepath_var}")


## ----------------------------------------


def read_env_list(list_var, default=None):
    ## Function to read and convert a list from an environmental variable

    res = [
        item.strip(" ")
        for item in str(os.getenv(list_var, "")).strip("([ ])").split(",")
        if item != ""
    ]

    if res:
        return res
    else:
        return default


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
            db_adapter.summary_pending_done_tasks()
        )

        ## Send an email with:
        ## count_success, count_error, count_pending

        ## To each address in:
        ## email_list

    except Exception as e:
        logging.error("daily summary email error=%s", str(e))


## ----------------------------------------


def task_daily_fetch_url(db_adapter, url_list):
    try:
        ## Fetch new information from each url in:
        ## url_list

        ## Optionally update the information in:
        ## db_adapter

        return

    except Exception as e:
        logging.error("daily summary email error=%s", str(e))
