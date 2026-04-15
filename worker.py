import uuid
import threading
from time import sleep, perf_counter
from enum import Enum

from task import Task


class Worker:
    class State(Enum):
        ACTIVE = "active"
        IDLE = "idle"

    def __init__(self, id):
        self.id = uuid.uuid4() if id is None else id
        self.state = Worker.State.IDLE

    def execute(self, task):
        # Task execution
        print(f"({int(perf_counter())%100}) Worker {self.id}: Task {task.id}: Starting processing")
        sleep(3)
        print(f"({int(perf_counter())%100}) Worker {self.id}: Task {task.id}: Completed")

        # Update final states
        self.state = Worker.State.IDLE
        task.status = Task.Status.DONE
        print(f"({int(perf_counter())%100}) Worker {self.id} is now IDLE")

    def process(self, task: Task):
        # Update the states
        self.state = Worker.State.ACTIVE
        task.status = Task.Status.IN_PROGRESS

        # Do the task
        thread = threading.Thread(target=self.execute, kwargs={"task": task})
        thread.start()

        # Return true (if task successful)  (NOTE: Used in later versions)
        return thread
