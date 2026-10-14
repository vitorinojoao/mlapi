"""Each process loop claims tasks with SKIP LOCKED; WORKER_COUNT controls parallel workers"""

import logging, os, time, uuid
from psycopg.types.json import Jsonb

from source.db_adapter import secret, connect

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"), format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("task-manager")

def creds(prefix): return secret(prefix+"_DB_USER"), secret(prefix+"_DB_PASSWORD")
def cfg(): u,p=creds("CONFIG"); return connect("config",u,p)
def data(): u,p=creds("DATA"); return connect("data",u,p)

def get_config():
    with cfg() as c, c.cursor() as cur:
        cur.execute("SELECT * FROM system_config ORDER BY config_id DESC LIMIT 1"); return cur.fetchone()

def process_one(order):
    task=None
    # Claim in a transaction; row lock ensures multiple workers don't process same task.
    with cfg() as c, c.cursor() as cur:
        cur.execute("SELECT p.task_id,p.user_id,p.created_at FROM pending_tasks p JOIN submission_outbox o USING(task_id) WHERE p.status='pending' AND o.state='complete' ORDER BY p.created_at "+("ASC" if order=="oldest" else "DESC")+" FOR UPDATE OF p SKIP LOCKED LIMIT 1")
        task=cur.fetchone()
        if not task: return False
        cur.execute("UPDATE pending_tasks SET status='processing' WHERE task_id=%s",(task["task_id"],))
    try:
        with data() as c, c.cursor() as cur:
            cur.execute("SELECT td.data_id, s.samples FROM task_data td JOIN samples s USING(data_id) WHERE td.task_id=%s",(task["task_id"],)); source=cur.fetchone()
        if not source: raise RuntimeError("sample_missing")
        # Replace this deterministic example transform with the actual workload.
        samples=source["samples"]
        if isinstance(samples,list): result={"sample_count":len(samples),"items":samples}
        else: result={"sample_count":len(samples),"keys":sorted(samples.keys())}
        result_id=uuid.uuid4()
        with data() as c, c.cursor() as cur:
            cur.execute("INSERT INTO results(results_id,result) VALUES (%s,%s)",(result_id,Jsonb(result)))
            cur.execute("UPDATE task_data SET results_id=%s WHERE task_id=%s",(result_id,task["task_id"]))
        with cfg() as c, c.cursor() as cur:
            cur.execute("INSERT INTO completed_tasks(task_id,user_id,created_at,completed_at,status) VALUES (%s,%s,%s,now(),'completed') ON CONFLICT(task_id) DO NOTHING",(task["task_id"],task["user_id"],task["created_at"]))
            cur.execute("DELETE FROM pending_tasks WHERE task_id=%s",(task["task_id"],))
            cur.execute("UPDATE submission_outbox SET state='processed' WHERE task_id=%s",(task["task_id"],))
        log.info("completed task_id=%s",task["task_id"]); return True
    except Exception as exc:
        log.exception("task failed task_id=%s",task["task_id"])
        with cfg() as c, c.cursor() as cur:
            cur.execute("UPDATE pending_tasks SET status='failed',error_code=%s WHERE task_id=%s",("processing_error",task["task_id"]))
        return True

def cleanup(conf):
    # Metadata remains in config; only samples/results/link rows are removed from data.
    with cfg() as c, c.cursor() as cur:
        if conf["pending_ttl_seconds"]:
            cur.execute("SELECT task_id FROM pending_tasks WHERE created_at < now() - (%s * interval '1 second')",(conf["pending_ttl_seconds"],)); old_pending=[r["task_id"] for r in cur.fetchall()]
        else: old_pending=[]
        if conf["completed_ttl_seconds"]:
            cur.execute("SELECT task_id FROM completed_tasks WHERE completed_at < now() - (%s * interval '1 second')",(conf["completed_ttl_seconds"],)); old_done=[r["task_id"] for r in cur.fetchall()]
        else: old_done=[]
    for tid in old_pending+old_done:
        with data() as c, c.cursor() as cur:
            cur.execute("DELETE FROM task_data WHERE task_id=%s RETURNING data_id,results_id",(tid,)); links=cur.fetchall()
            for link in links:
                if link["results_id"]: cur.execute("DELETE FROM results WHERE results_id=%s",(link["results_id"],))
                cur.execute("DELETE FROM samples WHERE data_id=%s",(link["data_id"],))
        # Metadata remains, status indicates that associated payload expired.
        with cfg() as c, c.cursor() as cur:
            cur.execute("UPDATE pending_tasks SET status='failed',error_code='expired' WHERE task_id=%s",(tid,))
    if old_pending or old_done: log.info("cleanup removed payload for %d tasks",len(old_pending)+len(old_done))

def worker_loop(index):
    log.info("worker %d started",index)
    while True:
        try:
            conf=get_config(); did=process_one(conf["task_order"])
            if not did: time.sleep(conf["worker_sleep_seconds"])
        except Exception: log.exception("worker loop error"); time.sleep(5)
