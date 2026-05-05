from __future__ import annotations
import multiprocessing
import threading
from time import sleep
from enum import Enum

from infra.logger import logger
from task import Task
from infra.task_queue import TaskQueue
from infra.config import REDIS_HOST, REDIS_PORT, REDIS_DB, HEARTBEAT_INTERVAL, MAX_IDLE_CYCLES


class Worker(multiprocessing.Process):

    class State(Enum):
        ACTIVE = "active"
        IDLE = "idle"

    # Shared-memory state codes (multiprocessing.Value needs a primitive)
    _STATE_IDLE = 0
    _STATE_ACTIVE = 1

    def __init__(self, worker_id, host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = REDIS_DB):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.host = host
        self.port = port
        self.db = db
        # Flag to check if process exited normally
        self.clean_exit = multiprocessing.Event()

        # Shared memory state flag (readable by external monitors)
        self._state_code = multiprocessing.Value('i', self._STATE_IDLE)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> Worker.State:
        """Read the worker's current state (safe to call from any process)."""
        with self._state_code.get_lock():
            code = self._state_code.value
        return Worker.State.IDLE if code == self._STATE_IDLE else Worker.State.ACTIVE

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _start_heartbeat(self, task_id) -> threading.Event:
        stop_event = threading.Event()

        def _beat():
            while not stop_event.is_set():
                stop_event.wait(timeout=HEARTBEAT_INTERVAL)
                if stop_event.is_set():
                    break

                still_valid = self._queue.heartbeat(task_id)
                if not still_valid:
                    logger.warning(f"Worker {self.worker_id}: Task {task_id}: processing key gone, watchdog reclaimed it")
                    stop_event.set()

        t = threading.Thread(target=_beat, daemon=True)
        t.start()
        return stop_event

    def _set_state(self, state: Worker.State):
        with self._state_code.get_lock():
            self._state_code.value = self._STATE_IDLE if state == Worker.State.IDLE else self._STATE_ACTIVE

    def _execute(self, task: Task) -> bool:
        """
        Execute the task, heartbeating throughout.
        Returns True if completed successfully, False if reclaimed.
        """
        # Task execution
        logger.info(f"Worker {self.worker_id}: Task {task.id}: Starting processing")
        stop_heartbeat = self._start_heartbeat(task.id)

        # Simulate work
        sleep(task.duration)

        # Check if the watchdog reclaimed task while this worker was executing it
        if stop_heartbeat.is_set():
            logger.warning(f"Worker {self.worker_id}: Task {task.id}: Aborted, reclaimed by watchdog")
            return False

        # Task is complete, Signal hearbeat to stop
        stop_heartbeat.set()
        logger.info(f"Worker {self.worker_id}: Task {task.id}: Completed")

        return True

    # ------------------------------------------------------------------
    # Main process
    # ------------------------------------------------------------------

    def run(self):
        """
        Worker loop runs continously to execute tasks.

        Queue connection is created after process forks, as redis connections are not reliable across fork boundaries.

        Shutdown contract:
            The worker exits naturally when BRPOP times out consecutively for MAX_IDLE_CYCLES cycles.
        """

        self._queue = TaskQueue(self.host, self.port, self.db)
        idle_cycles = 0

        logger.info(f"Worker {self.worker_id}: started process (pid={self.pid})")

        while idle_cycles < MAX_IDLE_CYCLES:
            # Blocks until a task is available up to TIMEOUT seconds
            task = self._queue.pop()

            if task is None:
                idle_cycles += 1
                logger.debug(f"Worker {self.worker_id}: queue empty (idle cycle {idle_cycles}/{MAX_IDLE_CYCLES})")
                continue

            idle_cycles = 0
            self._set_state(Worker.State.ACTIVE)
            logger.debug(f"Worker {self.worker_id}: ACTIVE")
            task.status = Task.Status.IN_PROGRESS

            success = self._execute(task)
            if success:
                self._queue.acknowledge(task.id)

            task.status = Task.Status.DONE
            self._set_state(Worker.State.IDLE)
            logger.debug(f"Worker {self.worker_id}: IDLE")

        logger.info(f"Worker {self.worker_id}: shutting down. No tasks after {MAX_IDLE_CYCLES} idle cycles")
        # Set this flag to indicate clean exit (flag not set indicates crash/abnormal exit)
        self.clean_exit.set()
