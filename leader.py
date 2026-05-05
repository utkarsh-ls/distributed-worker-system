from __future__ import annotations
import multiprocessing
import random
from time import sleep, time
from enum import Enum

from infra.logger import logger
from task import Task
from infra.task_queue import TaskQueue
from infra.election import ElectionClient
from infra.config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB,
    TASK_DURATION_MIN, TASK_DURATION_MAX,
    TASK_INTERVAL_MIN, TASK_INTERVAL_MAX,
)


class Leader(multiprocessing.Process):
    """
    The Leader pushes tasks into the queue. No knowledge of workers (akin to a producer).
    """

    def __init__(self, candidate_id: str, mode: ElectionClient.Mode, runtime: float = 0, num_tasks: int = 0,
                 host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = REDIS_DB):
        super().__init__(daemon=True, name=f"Leader-{candidate_id}")
        self.candidate_id = candidate_id
        self.mode = ElectionClient.Mode(mode)
        self.runtime = runtime
        self.num_tasks = num_tasks
        self.host = host
        self.port = port
        self.db = db
        # Flag to check if process exited normally
        self.clean_exit = multiprocessing.Event()

    def run(self):
        """
        Process entry point.

        Full leader lifecycle: elect → (optionally init state) → generate → release.
        Loops back to election if the mode condition hasn't been met yet.
        (e.g. a standby takes over mid-run after a crash).
        """
        self._queue = TaskQueue(self.host, self.port, self.db)
        self._election = ElectionClient(self.candidate_id, self.host, self.port, self.db)
        self._task_seq = 0          # Local seq. counter for task IDs

        # Block until this candidate wins the election
        self._election.wait_for_candidacy()
        self._election.start_lock_heartbeat()

        try:
            if self.mode == ElectionClient.Mode.RUNTIME:
                self._run_runtime_mode()
            else:
                self._run_num_tasks_mode()
            # Set this flag to indicate clean exit (flag not set indicates crash/abnormal exit)
            self.clean_exit.set()
        finally:
            self._election.stop_lock_heartbeat()
            self._election.release_lock()

    def _run_runtime_mode(self):
        # Determine remaining time: first elected leader init's the state, failover leaders read it
        remaining = self._election.get_remaining_runtime()
        if remaining is None:    # First leader, init state
            self._election.init_runtime_state(self.runtime)
            remaining = self.runtime
            logger.info(f"Leader {self.candidate_id} ({self.mode} mode): generating tasks for {remaining:1f}s")
        elif remaining <= 0.0:
            logger.info(f"Leader {self.candidate_id} ({self.mode} mode): runtime window passed, exiting")
            return
        else:
            logger.info(f"Leader {self.candidate_id} ({self.mode} mode): generating, {remaining:1f}s remaining")

        deadline = time() + remaining
        while time() < deadline:
            task = self._make_task()
            task_qsize = self._queue.push(task)
            logger.debug(f"Leader {self.candidate_id} ({self.mode} mode): generated Task {task.id} (Remaining={(deadline-time()):.1f}s, Queue size {task_qsize})")
            interval = random.uniform(TASK_INTERVAL_MIN, TASK_INTERVAL_MAX)
            sleep(interval)

        logger.info(f"Leader {self.candidate_id} ({self.mode} mode): runtime window complete")

    def _run_num_tasks_mode(self):
        # Determine remaining tasks: first elected leader init's the counter, failover leaders read it
        remaining = self._election.get_tasks_remaining()
        if remaining is None:      # First leader, init state
            self._election.init_task_counter(self.num_tasks)
            logger.info(f"Leader {self.candidate_id} ({self.mode} mode): generating, total {self.num_tasks} tasks")
        elif remaining <= 0:
            logger.info(f"Leader {self.candidate_id} ({self.mode} mode): generated all {self.num_tasks} tasks, exiting")
            return
        else:
            logger.info(f"Leader {self.candidate_id} ({self.mode} mode): generating, {remaining} tasks remaining")

        while True:
            remaining = self._election.decrement_tasks_remaining()
            if remaining < 0:
                self._election.increment_tasks_remaining()
                break

            task = self._make_task()
            task_qsize = self._queue.push(task)
            logger.debug(f"Leader {self.candidate_id} ({self.mode} mode): generated Task {task.id} (Remaining={remaining} tasks, Queue size {task_qsize})")
            interval = random.uniform(TASK_INTERVAL_MIN, TASK_INTERVAL_MAX)
            sleep(interval)

        logger.info(f"Leader {self.candidate_id} ({self.mode} mode): all tasks generated")

    def _make_task(self) -> Task:
        self._task_seq += 1
        duration = random.uniform(TASK_DURATION_MIN, TASK_DURATION_MAX)
        return Task(
            id=f"{self.candidate_id}-{self._task_seq}",
            payload={
                "job": f"task_{self.candidate_id}_{self._task_seq}",
                "duration": round(duration, 2),
            },
        )
