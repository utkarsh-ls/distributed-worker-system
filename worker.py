import multiprocessing
from time import sleep, perf_counter
from enum import Enum

from task import Task


class Worker(multiprocessing.Process):
    """
    A Worker is a real OS process. It pulls tasks off a shared
    multiprocessing.Queue and executes them one at a time.
 
    State is tracked via a multiprocessing.Value so the Leader
    can read it from a different process safely.
 
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
    
    def __init__(self, worker_id, task_queue: multiprocessing.Queue):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self._state_code = multiprocessing.Value('i', self._STATE_IDLE)    # Shared between leader and worker
        self.task_queue = task_queue    # Common queue for all workers


    @property
    def state(self) -> 'Worker.State':
        """Read the worker's current state (safe to call from any process)."""
        with self._state_code.get_lock():
            code = self._state_code.value
        return Worker.State.IDLE if code == self._STATE_IDLE else Worker.State.ACTIVE
    
    
    def _set_state(self, state: 'Worker.State'):
        with self._state_code.get_lock():
            self._state_code.value = self._STATE_IDLE if state==Worker.State.IDLE else self._STATE_ACTIVE
    
    def _execute(self, task: Task):
        """Simulate task execution"""
        # Task execution
        print(f"({int(perf_counter())%100}) Worker {self.worker_id}: Task {task.id}: Starting processing")
        sleep(3)
        print(f"({int(perf_counter())%100}) Worker {self.worker_id}: Task {task.id}: Completed")
        
    
    def run(self):
        """
        Event loop: block on the queue, execute tasks, repeat.
        Exits cleanly when it receives the sentinel value (None).
        """
        print(f"({int(perf_counter()) % 100:02d}) Worker {self.worker_id}: started process (pid={self.pid})")
 
        while True:
            task = self.task_queue.get()  # blocks until a task is available
 
            if task is None:              # sentinel (singals no more tasks): time to shut down
                print(f"({int(perf_counter()) % 100:02d}) Worker {self.worker_id}: received shutdown signal")
                break
 
            self._set_state(Worker.State.ACTIVE)
            print(f"({int(perf_counter()) % 100:02d}) Worker {self.worker_id}: ACTIVE")
            task.status = Task.Status.IN_PROGRESS
 
            self._execute(task)
 
            task.status = Task.Status.DONE
            self._set_state(Worker.State.IDLE)
            print(f"({int(perf_counter()) % 100:02d}) Worker {self.worker_id}: IDLE")
 
