"""db_adapter"""

import psycopg
from psycopg.rows import dict_row


class DatabaseAdapter:
    """Object to connect and communicate with a database"""

    def __init__(
        self,
        db_host,
        db_port,
        db_timeout,
        db_name,
        db_user,
        db_password,
        task_last_in_first_out,
        task_completed_time_to_live,
        task_pending_time_to_live,
    ):
        try:
            self.db_host = str(db_host)
            self.db_port = int(db_port)
            self.db_timeout = int(db_timeout)
            self.db_name = str(db_name)
            self.db_user = str(db_user)
            self.db_password = str(db_password)

        except Exception as e:
            raise ValueError("The database adapter must use str credentials") from e

        ## ----------------------------------------

        try:
            self.task_lifo_order = bool(task_last_in_first_out)

        except Exception as e:
            raise ValueError(
                "The order of 'last in first out' must be a boolean"
            ) from e

        try:
            self.task_completed_ttl_seconds = int(task_completed_time_to_live)

        except Exception as e:
            raise ValueError(
                "The 'time to live' of completed tasks"
                + " must be an integer number of seconds"
            ) from e

        try:
            self.task_pending_ttl_seconds = int(task_pending_time_to_live)

        except Exception as e:
            raise ValueError(
                "The 'time to live' of pending tasks"
                + " must be an integer number of seconds"
            ) from e

        if self.task_completed_ttl_seconds < 1:
            raise ValueError(
                "The 'time to live' of completed tasks must be at least 1 second"
            )

        if self.task_pending_ttl_seconds < 1:
            raise ValueError(
                "The 'time to live' of pending tasks must be at least 1 second"
            )

        ## ----------------------------------------

    def connect(self, autocommit=False):
        """Create a connection to the database"""

        return psycopg.connect(
            host=self.db_host,
            port=self.db_port,
            connect_timeout=self.db_timeout,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
            autocommit=autocommit,
            row_factory=dict_row,
        )

    def db_claim_task(self):
        # Claim tasks with SKIP LOCKED so that multiple workers don't process the same task

        with self.connect() as c, c.cursor() as cur:
            cur.execute(
                "SELECT p.task_id,p.user_id,p.created_at FROM pending_tasks p JOIN submission_outbox o USING(task_id) WHERE p.status='pending' AND o.state='complete' ORDER BY p.created_at "
                + ("ASC" if self.task_lifo_order else "DESC")
                + " FOR UPDATE OF p SKIP LOCKED LIMIT 1"
            )
            task = cur.fetchone()
            if not task:
                return False
            cur.execute(
                "UPDATE pending_tasks SET status='processing' WHERE task_id=%s",
                (task["task_id"],),
            )
            cur.execute(
                "SELECT td.data_id, s.samples FROM task_data td JOIN samples s USING(data_id) WHERE td.task_id=%s",
                (task["task_id"],),
            )
            source = cur.fetchone()

            return task, source

    def db_task_completed(self, task_id, result):
        with self.connect() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO results(results_id,result) VALUES (%s,%s)",
                (result_id, Jsonb(result)),
            )
            cur.execute(
                "UPDATE task_data SET results_id=%s WHERE task_id=%s",
                (result_id, task["task_id"]),
            )
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

    def db_task_failed(self, task_id):
        with self.connect() as c, c.cursor() as cur:
            cur.execute(
                "UPDATE pending_tasks SET status='failed',error_code=%s WHERE task_id=%s",
                ("processing_error", task["task_id"]),
            )
