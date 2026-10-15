"""Independent manager"""

import logging, os, threading, time

from source.ml_tasks import worker_loop, get_config, cleanup

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"), format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("task-manager")

def main():
    while True:
        try:
            log.info("worker")
            # conf=get_config(); cleanup(conf)
            # desired=conf["worker_count"]
            # threads=[t for t in threading.enumerate() if t.name.startswith("task-worker-") and t.is_alive()]
            # for i in range(len(threads),desired):
            #     threading.Thread(target=worker_loop,args=(i+1,),daemon=True,name=f"task-worker-{i+1}").start()
            # time.sleep(max(5,conf["worker_sleep_seconds"]))
        except Exception:
            log.exception("manager loop error")
        
        time.sleep(10)
        
if __name__=="__main__":
    main()

