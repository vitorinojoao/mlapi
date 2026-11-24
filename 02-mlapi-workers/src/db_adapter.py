"""db_adapter"""

from psycopg_pool import ConnectionPool

# from psycopg.rows import dict_row, tuple_row
# from psycopg.types.json import Jsonb


class DBAdapter:
    """Object to connect and communicate with a database"""

    def __init__(
        self,
        db_host,
        db_port,
        db_name,
        db_user,
        db_password,
        db_pool_min,
        db_pool_max,
        db_pool_workers,
        db_pool_timeout,
        tasks_order_last_in_first_out=None,
        tasks_summary_hours=None,
        tasks_pending_time_to_live=None,
        tasks_done_time_to_live=None,
        input_data_time_to_live=None,
        output_results_time_to_live=None,
    ):
        try:
            db_host = str(db_host)
            db_port = str(int(db_port))
            db_name = str(db_name)
            db_user = str(db_user)
            db_password = str(db_password)

        except Exception as e:
            raise ValueError(
                "The DB Adapter requires valid connection credentials"
            ) from e

        ## ----------------------------------------

        try:
            db_pool_min = int(db_pool_min)
            db_pool_max = int(db_pool_max)
            db_pool_workers = int(db_pool_workers)
            db_pool_timeout = int(db_pool_timeout)

        except Exception as e:
            raise ValueError(
                "The DB Adapter requires a valid connection pool configuration"
            ) from e

        ## ----------------------------------------

        try:
            self.tasks_order_by = (
                "DESC"
                if tasks_order_last_in_first_out is None
                or bool(tasks_order_last_in_first_out)
                else "ASC"
            )

        except Exception as e:
            raise ValueError(
                "The DB tasks order must use True for LIFO or False for FIFO"
            ) from e

        ## ----------------------------------------

        if tasks_summary_hours:
            try:
                self.tasks_summary_hours = int(tasks_summary_hours)

            except Exception as e:
                raise ValueError(
                    "The DB tasks summary must use an integer number of hours"
                ) from e

            if self.tasks_summary_hours < 1:
                raise ValueError("The DB tasks summary must use at least 1 hour")

        else:
            self.tasks_summary_hours = 24

        ## ----------------------------------------

        if tasks_pending_time_to_live:
            try:
                self.tasks_pending_ttl = int(tasks_pending_time_to_live)

            except Exception as e:
                raise ValueError(
                    "The DB 'time to live' of pending tasks"
                    + " must be an integer number of seconds"
                ) from e

            if self.tasks_pending_ttl < 1:
                raise ValueError(
                    "The DB 'time to live' of pending tasks must be at least 1 second"
                    + ", or None to disable expiration"
                )

        else:
            self.tasks_pending_ttl = None

        ## ----------------------------------------

        if tasks_done_time_to_live:
            try:
                self.tasks_done_ttl = int(tasks_done_time_to_live)

            except Exception as e:
                raise ValueError(
                    "The DB 'time to live' of done tasks"
                    + " must be an integer number of seconds"
                ) from e

            if self.tasks_done_ttl < 1:
                raise ValueError(
                    "The DB 'time to live' of done tasks must be at least 1 second"
                    + ", or None to disable expiration"
                )

        else:
            self.tasks_done_ttl = None

        ## ----------------------------------------

        if input_data_time_to_live:
            try:
                self.input_data_ttl = int(input_data_time_to_live)

            except Exception as e:
                raise ValueError(
                    "The DB 'time to live' of input data"
                    + " must be an integer number of seconds"
                ) from e

            if self.input_data_ttl < 1:
                raise ValueError(
                    "The DB 'time to live' of input data must be at least 1 second"
                    + ", or None to disable expiration"
                )

        else:
            self.input_data_ttl = None

        ## ----------------------------------------

        if output_results_time_to_live:
            try:
                self.output_results_ttl = int(output_results_time_to_live)

            except Exception as e:
                raise ValueError(
                    "The DB 'time to live' of output results"
                    + " must be an integer number of seconds"
                ) from e

            if self.output_results_ttl < 1:
                raise ValueError(
                    "The DB 'time to live' of output results must be at least 1 second"
                    + ", or None to disable expiration"
                )

        else:
            self.output_results_ttl = None

        ## ----------------------------------------

        self.pool = ConnectionPool(
            conninfo=(
                f"host={db_host}"
                f" port={db_port}"
                f" dbname={db_name}"
                f" user={db_user}"
                f" password={db_password}"
            ),
            min_size=db_pool_min,
            max_size=db_pool_max,
            num_workers=db_pool_workers,
            timeout=db_pool_timeout,
            kwargs={"autocommit": False},
            open=True,
        )

    ## ----------------------------------------

    def close(self):
        self.pool.close()

    ## ----------------------------------------

    def claim_pending_task(self):
        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                """
                WITH claimed AS (
                    SELECT task_id
                    FROM tasks_pending
                    ORDER BY created_at %s
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                ),
                deleted AS (
                    DELETE FROM tasks_pending tp
                    USING claimed c
                    WHERE tp.task_id = c.task_id
                    RETURNING tp.task_id, tp.user_id, tp.created_at
                ),
                inserted AS (
                    INSERT INTO tasks_done (task_id, user_id, created_at)
                    SELECT task_id, user_id, created_at
                    FROM deleted
                )
                SELECT tdl.task_id, tin.input_data
                FROM deleted tdl
                LEFT JOIN input_data tin
                ON tdl.task_id = tin.task_id
                ;
                """,
                (self.tasks_order_by,),
            )

            return cur.fetchone()

    ## ----------------------------------------

    def register_task_success(self, task_id, output_results, success_message):
        try:
            output_results = [str(o) for o in output_results]

        except Exception as e:
            raise ValueError(
                "The DB currently requires output results to be a list of str"
            ) from e

        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                """
                WITH updated AS (
                    UPDATE tasks_done
                    SET done_at = CURRENT_TIMESTAMP,
                        done_success = TRUE,
                        done_message = %s
                    WHERE task_id = %s
                    RETURNING task_id, user_id
                )
                INSERT INTO output_results (task_id, user_id, output_results)
                SELECT updated.task_id, updated.user_id, %s
                FROM updated
                ;
                """,
                (success_message, task_id, output_results),
            )

    ## ----------------------------------------

    def register_task_error(self, task_id, error_message):
        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                """
                UPDATE tasks_done
                SET done_at = CURRENT_TIMESTAMP,
                    done_success = FALSE,
                    done_message = %s
                WHERE task_id = %s
                ;
                """,
                (error_message, task_id),
            )

    ## ----------------------------------------

    def cleanup_input_output(self):
        if self.input_data_ttl and self.output_results_ttl:
            query = """
                WITH deleted_input AS (
                    DELETE FROM input_data 
                    WHERE task_id IN (
                        SELECT task_id
                        FROM tasks_done
                        WHERE created_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                    )
                )
                DELETE FROM output_results 
                WHERE task_id IN (
                    SELECT task_id
                    FROM tasks_done
                    WHERE done_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                );
                """
            args = (self.input_data_ttl, self.output_results_ttl)

        elif self.input_data_ttl:
            query = """
                DELETE FROM input_data 
                WHERE task_id IN (
                    SELECT task_id
                    FROM tasks_done
                    WHERE created_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                );
                """
            args = (self.input_data_ttl,)

        elif self.output_results_ttl:
            query = """
                DELETE FROM output_results 
                WHERE task_id IN (
                    SELECT task_id
                    FROM tasks_done
                    WHERE done_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                );
                """
            args = (self.output_results_ttl,)

        else:
            return

        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(query, args)

    ## ----------------------------------------

    def cleanup_pending_done_tasks(self):
        if self.tasks_pending_ttl and self.tasks_done_ttl:
            subquery = """
                WITH deleted_pending AS (
                    DELETE FROM tasks_pending
                    WHERE created_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                    RETURNING task_id
                ),
                deleted_done AS (
                    DELETE FROM tasks_done
                    WHERE done_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                    RETURNING task_id
                ),
                deleted_tasks AS (
                    SELECT task_id FROM deleted_pending
                    UNION ALL
                    SELECT task_id FROM deleted_done
                ),
                """
            args = (self.tasks_pending_ttl, self.tasks_done_ttl)

        elif self.tasks_pending_ttl:
            subquery = """
                WITH deleted_tasks AS (
                    DELETE FROM tasks_pending
                    WHERE created_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                    RETURNING task_id
                ),
                """
            args = (self.tasks_pending_ttl,)

        elif self.tasks_done_ttl == 0:
            subquery = """
                WITH deleted_tasks AS (
                    DELETE FROM tasks_done
                    WHERE done_at < CURRENT_TIMESTAMP - make_interval(secs => %s)
                    RETURNING task_id
                ),
                """
            args = (self.tasks_done_ttl,)

        else:
            return

        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                subquery + """
                deleted_input AS (
                    DELETE FROM input_data 
                    WHERE task_id IN (
                        SELECT task_id
                        FROM deleted_tasks
                    )
                )
                DELETE FROM output_results 
                WHERE task_id IN (
                    SELECT task_id
                    FROM deleted_tasks
                );
                """,
                args,
            )

    ## ----------------------------------------

    def summary_pending_done_tasks(self):
        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                """
                WITH csuc AS (
                    SELECT COUNT(task_id) AS count_success
                    FROM tasks_done
                    WHERE done_success = TRUE
                        AND done_at >= CURRENT_TIMESTAMP - INTERVAL '%s hours'
                        AND done_at < CURRENT_TIMESTAMP
                ),
                cerr AS (
                    SELECT COUNT(task_id) AS count_error
                    FROM tasks_done
                    WHERE done_success = FALSE
                        AND done_at >= CURRENT_TIMESTAMP - INTERVAL '%s hours'
                        AND done_at < CURRENT_TIMESTAMP
                ),
                cpen AS (
                    SELECT COUNT(task_id) AS count_pending
                    FROM tasks_pending
                )
                SELECT csuc.count_success, cerr.count_error, cpen.count_pending
                FROM csuc, cerr, cpen;
                ;
                """,
                (self.tasks_summary_hours, self.tasks_summary_hours),
            )

            return cur.fetchone()
