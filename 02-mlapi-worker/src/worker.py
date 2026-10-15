"""worker"""

import logging
from apscheduler.schedulers.background import BlockingScheduler


def create_workers():
    db_adapter = None

    # Create the Scheduler with max tasks and job defaults
    bscheduler = BlockingScheduler(
        executors={
            "processpool": {
                "type": "processpool",
                "max_workers": 1,
                "pool_kwargs": {"max_tasks_per_child": 2},
            },
        },
        job_defaults={"coalesce": True, "max_instances": 1},
    )

    # Create job for 'type' correlations
    bscheduler.add_job(
        job_type_correlations,
        trigger="interval",
        seconds=60,
        args=[db_adapter],
        id="job_type_correlations",
    )
    logging.warning("job_type_correlations added")

    # Create job for 'type @ source' correlations
    bscheduler.add_job(
        job_type_source_correlations,
        trigger="interval",
        seconds=60,
        args=[db_adapter],
        id="job_type_source_correlations",
    )
    logging.warning("job_type_source_correlations added")

    # Start the Scheduler
    try:
        bscheduler.start()

    except (KeyboardInterrupt, SystemExit):
        logging.warning("scheduler ordered to stop")

    finally:
        bscheduler.shutdown()
        logging.warning("scheduler stopped")
