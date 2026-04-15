from enum import Enum
import uuid

class Task:
    class Status(Enum):
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        DONE = "done"
    
    def __init__ (self, id):
        self.id = uuid.uuid4() if id is None else id
        self.payload = None
        self.status = self.Status.PENDING
