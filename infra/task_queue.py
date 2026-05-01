import json
import redis
from typing import Optional

from task import Task
from infra.config import QUEUE_KEY, PROCESSING_KEY, PROCESSING_TTL, BRPOP_TIMEOUT, EXPIRY_CHECK_THRESHOLD


class TaskQueue:
    def __init__(self, host: str = "127.0.0.1", port: int = 6379, db: int = 0):
        # Enable decode_response to return string instead of bytes
        self._r = redis.Redis(host=host, port=port,
                              db=db, decode_responses=True)

    # ------------------------------------------------------------------
    # Producer API  (used by Leader)
    # ------------------------------------------------------------------

    def push(self, task: Task) -> int:
        """
        Enqueue a task (using Redis LPUSH).

        LPUSH is atomic: can be called from multiple leaders simultaneously.

        Args:
            task (Task): Task to be added to the task queue.

        Returns:
            int: The new length of the queue.
        """
        serialized = json.dumps(task.to_dict())
        queue_len = self._r.lpush(QUEUE_KEY, serialized)

        return queue_len

    # ------------------------------------------------------------------
    # Consumer API  (used by Worker)
    # ------------------------------------------------------------------

    def pop(self, timeout: Optional[int] = None) -> Optional[Task]:
        """
        Dequeue the next task (using Redis BRPOP), blocking for up to `timeout` seconds.
        Immediately register it as in-flight.

        BRPOP returns a (key, value) tuple, or None on timeout. Key is always QUEUE_KEY (used in LPUSH).

        Uses a pipeline to make (BRPOP+SET) atomic.

        Args:
            timeout (int, optional): Maximum time to wait in seconds. Overrides the instance's default timeout if provided.

        Returns:
            Task | None: The next available task if one is dequeued within the timeout; otherwise, None.
        """
        timeout = BRPOP_TIMEOUT if timeout is None else timeout
        result = self._r.brpop(QUEUE_KEY, timeout=timeout)
        if result is None:
            return None

        _, serialized = result
        task = Task.from_dict(json.loads(serialized))

        processing_key = PROCESSING_KEY.format(task.id)
        # Register the task as `in-flight`, store full task data so `Watchdog`` can re-queue it intact.
        self._r.set(processing_key, serialized, ex=PROCESSING_TTL)

        return task

    def heartbeat(self, task_id) -> bool:
        """
        Renew the TTL on a processing key.
        To be called periodically by worker when executing a task.

        Args:
            task_id: ID of the task for which key is to be renewed.

        Returns:
            bool: False, if key no longer exists (eg: watchdog already re-queued it), signals worker to abort. Else, True.
        """
        processing_key = PROCESSING_KEY.format(task_id)
        return bool(self._r.expire(processing_key, PROCESSING_TTL))

    def acknowledge(self, task_id) -> None:
        """
        Mark a task as successfully completed.
        > Deletes the processing key.

        Args:
            task_id: ID of the task to be acknowledged.
        """

        processing_key = PROCESSING_KEY.format(task_id)
        self._r.delete(processing_key)

    # ------------------------------------------------------------------
    # Watchdog API  (used by Watchdog)
    # ------------------------------------------------------------------

    def get_expiring_tasks(self) -> list[Task]:
        """
        Scan for processing keys whose TTL is near expiry.

        Redis deletes expired keys lazily: they disappear when accessed or when the background expiry sweep runs.
        SCAN with a pattern finds all processing keys (`processing:*`) that still exist.
        Any that are missing have already expired and need recovery.

        Returns:
            list[Task]: A list of tasks nearing expiration (0<`ttl`≤1)
        """
        # Scan all in-flight registrations
        expired = []
        cursor = 0
        pattern = PROCESSING_KEY.format("*")

        while True:
            cursor, keys = self._r.scan(cursor, match=pattern, count=100)
            for key in keys:
                # ttl >  0: still alive.
                # ttl = -1: no expiry set (shouldn't happen).
                # ttl = -2: key gone. We won't see -2 here since SCAN only
                ttl = self._r.ttl(key)

                # returns existing keys, but a very low TTL means near-expiry.
                # We re-queue anything with TTL <= expiry_threshold to catch it before it disappears and becomes unrecoverable.
                if 0 < ttl <= EXPIRY_CHECK_THRESHOLD:
                    raw = self._r.get(key)
                    if raw:
                        expired.append(Task.from_dict(json.loads(raw)))

            if cursor == 0:
                break

        return expired

    def requeue(self, task: Task) -> None:
        """
        Re-push a task into waiting queue, and remove its processing key.
        Called by watchdog for recovered tasks.

        Args:
            task (Task): recovered Task object to be re-pushed into waiting queue.
        """
        task.status = Task.Status.PENDING
        serialized = json.dumps(task.to_dict())
        processing_key = PROCESSING_KEY.format(task.id)

        # Pipeline: delete processing key + re-push
        pipe = self._r.pipeline()
        pipe.delete(processing_key)
        pipe.lpush(QUEUE_KEY, serialized)
        pipe.execute()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def depth(self) -> int:
        """Current size of the queue."""
        return self._r.llen(QUEUE_KEY)

    def clear(self) -> None:
        """Flush the queue. Delete all keys"""
        # Delete the main queue
        self._r.delete(QUEUE_KEY)

        # Delete in-flight keys
        cursor = 0
        pattern = PROCESSING_KEY.format("*")
        while True:
            cursor, keys = self._r.scan(cursor, match=pattern, count=100)
            if keys:
                self._r.delete(*keys)
            if cursor == 0:
                break
