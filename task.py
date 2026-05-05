from __future__ import annotations
from enum import Enum


class Task:
    class Status(Enum):
        PENDING = "pending"
        IN_PROGRESS = "in_progress"
        DONE = "done"

    def __init__(self, id: int | str, payload: dict):
        """
        payload must include a 'duration' key (float, seconds) set by
        the leader at generation time. Workers read this to know how
        long to simulate execution.

        Example payload:
            {"job": "resize_image", "duration": 4.7}
        """
        self.id = id
        self.payload = payload
        self.status = Task.Status.PENDING
    
    @property
    def duration(self) -> float:
        return float(self.payload.get("duration", 3.0))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "payload": self.payload,
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Task:
        task = cls(id=data["id"], payload = data.get("payload", {}))
        task.status = Task.Status(data["status"])
        
        return task
    
    def __repr__(self):
        return f"Task(id={self.id}, status={self.status.value})"