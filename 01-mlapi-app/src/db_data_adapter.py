"""db_data_adapter"""

from psycopg_pool import ConnectionPool

# from psycopg.rows import tuple_row
# from psycopg.types.json import Jsonb


class DBDataAdapter:
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

    def register_pending_task(self, user_id, input_data):
        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                """
                WITH inserted AS (
                    INSERT INTO tasks_pending (user_id)
                    VALUES (%s)
                    RETURNING task_id
                )
                INSERT INTO input_data (task_id, input_data)
                SELECT task_id, %s
                FROM inserted
                RETURNING task_id
                ;
                """,
                (user_id, input_data),
            )

            return cur.fetchone()

    ## ----------------------------------------

    def fetch_task_results(self, user_id, task_id):
        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                """
                SELECT tor.output_results
                FROM output_results tor
                WHERE tor.task_id = %s
                    AND tor.user_id = %s
                ;
                """,
                (task_id, user_id),
            )

            return cur.fetchone()

    ## ----------------------------------------

    def check_task_status(self, user_id, task_id):
        with self.pool.connect() as c, c.cursor() as cur:
            cur.execute(
                """
                WITH fetched AS (
                    SELECT created_at,
                        NULL::TIMESTAMPTZ AS claimed_at,
                        NULL::TIMESTAMPTZ AS done_at,
                        NULL::BOOL AS done_success,
                        NULL::TEXT AS done_message
                    FROM tasks_pending
                    WHERE task_id = %s
                        AND user_id = %s
                )
                SELECT *
                FROM fetched
                UNION ALL
                SELECT created_at,
                    claimed_at,
                    done_at,
                    done_success,
                    done_message
                FROM tasks_done
                WHERE task_id = %s
                    AND user_id = %s
                    AND NOT EXISTS (SELECT 1 FROM fetched)
                ;
                """,
                (task_id, user_id, task_id, user_id),
            )

            return cur.fetchone()
