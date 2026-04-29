from __future__ import annotations
import multiprocessing
from time import sleep, perf_counter
from enum import Enum

from task import Task
from infra.task_queue import TaskQueue

MAX_IDLE_CYCLES = 3  # exit after this many consecutive timeouts


class Worker(multiprocessing.Process):
    """
    A fully independent OS process, knows nothing about the leader (akin to a consumer). Connects to queue directly, repeatedly pops and executes tasks.

    State transitions:
        IDLE -> ACTIVE  (when a task is picked up)
        ACTIVE -> IDLE  (when the task completes)
    """

    class State(Enum):
        ACTIVE = "active"
        IDLE = "idle"

    # Shared-memory state codes (multiprocessing.Value needs a primitive)
    _STATE_IDLE = 0
    _STATE_ACTIVE = 1

    def __init__(self, worker_id,  host: str = "127.0.0.1", port: int = 6379):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.host = host
        self.port = port

        # Shared memory state flag (readable by external monitors)
        self._state_code = multiprocessing.Value('i', self._STATE_IDLE)

    @property
    def state(self) -> Worker.State:
        """Read the worker's current state (safe to call from any process)."""
        with self._state_code.get_lock():
            code = self._state_code.value
        return Worker.State.IDLE if code == self._STATE_IDLE else Worker.State.ACTIVE

    def _set_state(self, state: Worker.State):
        with self._state_code.get_lock():
            self._state_code.value = self._STATE_IDLE if state == Worker.State.IDLE else self._STATE_ACTIVE

    def _execute(self, task: Task):
        """Simulate task execution"""
        # Task execution
        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: Task {task.id}: Starting processing")
        sleep(3)
        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: Task {task.id}: Completed")

    def run(self):
        """
        Worker loop to execute tasks.

        Shutdown contract:
            The worker exits naturally when BRPOP times out consecutively for MAX_IDLE_CYCLES cycles.
        """

        queue = TaskQueue(self.host, self.port)
        idle_cycles = 0

        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: started process (pid={self.pid})")

        while idle_cycles < MAX_IDLE_CYCLES:
            # Blocks until a task is available up to TIMEOUT seconds
            task = queue.pop()

            if task is None:
                idle_cycles += 1
                print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: queue empty (idle cycle {idle_cycles}/{MAX_IDLE_CYCLES})")
                continue

            idle_cycles = 0
            self._set_state(Worker.State.ACTIVE)
            print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: ACTIVE")
            task.status = Task.Status.IN_PROGRESS

            self._execute(task)

            task.status = Task.Status.DONE
            self._set_state(Worker.State.IDLE)
            print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: IDLE")

        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: shutting down. No tasks after {MAX_IDLE_CYCLES} idle cycles")
