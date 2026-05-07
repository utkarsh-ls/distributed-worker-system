import multiprocessing
from time import sleep

from infra.logger import logger
from infra.metrics import tasks_recovered_total
from infra.task_queue import TaskQueue
from infra.config import REDIS_HOST, REDIS_PORT, REDIS_DB, SCAN_INTERVAL


class Watchdog(multiprocessing.Process):
    def __init__(self, host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = REDIS_DB):
        super().__init__(daemon=True, name="Watchdog")
        self.host = host
        self.port = port
        self.db = db

        # Signal from main.py to stop gracefully
        self._stop_flag = multiprocessing.Event()

    def stop(self):
        self._stop_flag.set()

    def run(self):
        queue = TaskQueue(self.host, self.port, self.db)
        logger.info(f"Watchdog: started (pid={self.pid})")

        while not self._stop_flag.is_set():
            expired = queue.get_expiring_tasks()

            for task in expired:
                logger.warning(f"Watchdog: recovering Task {task.id}: TTL expired, re-queueing")
                queue.requeue(task)
                tasks_recovered_total.inc()

            sleep(SCAN_INTERVAL)

        logger.info(f"Watchdog: shutdown")
