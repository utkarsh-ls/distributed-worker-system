from enum import Enum


class Task:
    class Status(Enum):
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        DONE = "done"

    def __init__(self, id):
        self.id = id
        self.payload = None
        self.status = Task.Status.PENDING

    def __repr__(self):
        return f"Task(id={self.id}, status={self.status.value})"