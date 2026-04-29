import json
import redis
from typing import Optional

from task import Task

QUEUE_KEY = "task_queue"    # Redis Queue name/id key


class TaskQueue:
    def __init__(self, host: str = "127.0.0.1", port: int = 6379, timeout: int = 5, db: int = 0):
        # Enable decode_response to return string instead of bytes
        self._r = redis.Redis(host=host, port=port,
                              db=db, decode_responses=True)
        self.brpop_timeout = timeout

    def push(self, task: Task) -> int:
        """
        Enqueue a task (using Redis LPUSH).

        LPUSH is atomic: if 2 leaders push simultaneously, their items are inserted as a single unit. No partial writes.

        Args:
            task (Task): Task to be added to the task queue.

        Returns:
            int: The new length of the queue.
        """
        serialized = json.dumps(task.to_dict())
        queue_len = self._r.lpush(QUEUE_KEY, serialized)

        return queue_len

    def pop(self, timeout: Optional[int] = None) -> Optional[Task]:
        """
        Dequeue the next task (using Redis BRPOP), blocking for up to `timeout` seconds.

        BRPOP returns a (key, value) tuple, or None on timeout. Key is always QUEUE_KEY (used in LPUSH).

        Args:
            timeout (int, optional): Maximum time to wait in seconds. Overrides the instance's default timeout if provided.

        Returns:
            Task | None: The next available task if one is dequeued within the timeout; otherwise, None.
        """
        timeout = self.brpop_timeout if timeout is None else timeout
        result = self._r.brpop(QUEUE_KEY, timeout=timeout)

        if result is None:
            return None
        _, serialized = result

        return Task.from_dict(json.loads(serialized))

    def depth(self) -> int:
        """Current size of the queue."""
        return self._r.llen(QUEUE_KEY)

    def clear(self) -> None:
        """Flush the queue."""
        self._r.delete(QUEUE_KEY)
