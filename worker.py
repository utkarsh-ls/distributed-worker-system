from __future__ import annotations
import multiprocessing
import threading
from time import sleep, perf_counter
from enum import Enum

from task import Task
from infra.task_queue import TaskQueue
from infra.config import HEARTBEAT_INTERVAL, MAX_IDLE_CYCLES, TASK_COMPLETION_TIME


class Worker(multiprocessing.Process):

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
                    print(f"({int(perf_counter()) % 100:02d}) Worker {self.worker_id}: Task {task_id}: processing key gone, watchdog reclaimed it")
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
        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: Task {task.id}: Starting processing")
        stop_heartbeat = self._start_heartbeat(task.id)
        
        # Simulate work
        sleep(TASK_COMPLETION_TIME)
        
        # Check if the watchdog reclaimed task while this worker was executing it
        if stop_heartbeat.is_set():
            print(f"({int(perf_counter()) % 100:02d}) Worker {self.worker_id}: Task {task.id}: Aborted, reclaimed by watchdog")
            return False
        
        # Task is complete, Signal hearbeat to stop
        stop_heartbeat.set()
        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: Task {task.id}: Completed")
        
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

        self._queue = TaskQueue(self.host, self.port)
        idle_cycles = 0

        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: started process (pid={self.pid})")

        while idle_cycles < MAX_IDLE_CYCLES:
            # Blocks until a task is available up to TIMEOUT seconds
            task = self._queue.pop()

            if task is None:
                idle_cycles += 1
                print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: queue empty (idle cycle {idle_cycles}/{MAX_IDLE_CYCLES})")
                continue

            idle_cycles = 0
            self._set_state(Worker.State.ACTIVE)
            print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: ACTIVE")
            task.status = Task.Status.IN_PROGRESS

            success = self._execute(task)
            if success:
                self._queue.acknowledge(task.id)

            task.status = Task.Status.DONE
            self._set_state(Worker.State.IDLE)
            print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: IDLE")

        print(f"({int(perf_counter())%100:02d}) Worker {self.worker_id}: shutting down. No tasks after {MAX_IDLE_CYCLES} idle cycles")
