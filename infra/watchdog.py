import multiprocessing
from time import sleep, perf_counter

from infra.task_queue import TaskQueue
from infra.config import SCAN_INTERVAL


class Watchdog(multiprocessing.Process):
    def __init__(self, host: str = "127.0.0.1", port: int = 6379):
        super().__init__(daemon=True, name="Watchdog")
        self.host = host
        self.port = port

        # Signal from main.py to stop gracefully
        self._stop_flag = multiprocessing.Event()

    def stop(self):
        self._stop_flag.set()

    def run(self):
        queue = TaskQueue(self.host, self.port)
        print(f"({int(perf_counter())%100:02d}) Watchdog: started (pid={self.pid})")

        while not self._stop_flag.is_set():
            expired = queue.get_expiring_tasks()

            for task in expired:
                print(f"({int(perf_counter())%100:02d}) Watchdog: recovering Task {task.id}: TTL expired, re-queueing")
                queue.requeue(task)

            sleep(SCAN_INTERVAL)

        print(f"({int(perf_counter())%100:02d}) Watchdog: shutdown")
