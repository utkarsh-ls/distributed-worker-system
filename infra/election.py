import json
import threading
from time import sleep, time
from typing import Optional
from enum import Enum
import redis

from infra.logger import logger
from infra.config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB,
    LEADER_LOCK_KEY, LEADER_RUNTIME_KEY, TASKS_REMAINING_KEY,
    LEADER_TTL, LEADER_HEARTBEAT_INTERVAL, ELECTION_POLL_INTERVAL
)


class ElectionClient:

    class Mode(Enum):
        RUNTIME = "runtime"
        NUM_TASKS = "num_tasks"

    def __init__(self, candidate_id: str, host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = REDIS_DB):
        self.candidate_id = candidate_id
        self._r = redis.Redis(host=host, port=port,
                              db=db, decode_responses=True)
        self._heartbeat_stop: Optional[threading.Event] = None

    # ------------------------------------------------------------------
    # Lock acquisition
    # ------------------------------------------------------------------

    def try_acquire_lock(self) -> bool:
        """
        Single atomic attempt to acquire the leader lock.

        SET nx=True ex=TTL: set only if key absent, with expiry.
        Both flags are applied in one command, no window between acquiring the lock and setting its TTL.

        Returns:
            bool: True, if this candidate is now the leader. Else, False.
        """
        acquired = self._r.set(
            LEADER_LOCK_KEY,
            self.candidate_id,
            nx=True,
            ex=LEADER_TTL
        )

        return acquired is True

    def wait_for_candidacy(self) -> None:
        """
        Blocking standby loop. Returns only when this candidate
        has won an election (i.e. try_acquire_lock() succeeds).

        Polls at ELECTION_POLL_INTERVAL so standbys don't hammer Redis.
        """
        logger.info(f"Candidate {self.candidate_id}: standing by for election ...")
        while not self.try_acquire_lock():
            sleep(ELECTION_POLL_INTERVAL)
        logger.info(f"Candidate {self.candidate_id}: WON election, Now leader")

    def release_lock(self) -> None:
        """
        Voluntarily release the lock on clean shutdown.
        A crashed leader never calls this, TTL handles that case.

        Only deletes the key if candidate still own it.
        (guards against a rare race where its TTL expired and another leader took over just before we called release).
        """
        current = self._r.get(LEADER_LOCK_KEY)
        if current == self.candidate_id:
            self._r.delete(LEADER_LOCK_KEY)
            logger.info(f"Leader {self.candidate_id}: Lock released")

    # ------------------------------------------------------------------
    # Lock heartbeat (runs while leader is active)
    # ------------------------------------------------------------------

    def start_lock_heartbeat(self) -> None:
        """
        Start a daemon thread that renews the leader lock TTL every heartbeat.
        Thread dies with the process on SIGKILL.
        """
        self._heartbeat_stop = threading.Event()

        def _beat():
            while not self._heartbeat_stop.is_set():
                self._heartbeat_stop.wait(timeout=LEADER_HEARTBEAT_INTERVAL)
                if self._heartbeat_stop.is_set():
                    break
                # Renew if lock is still owned, Else stop.
                current = self._r.get(LEADER_LOCK_KEY)
                if current != self.candidate_id:
                    logger.warning(f"Leader {self.candidate_id}: Lost lock, stopping heartbeat")
                    self._heartbeat_stop.set()
                    break
                self._r.expire(LEADER_LOCK_KEY, LEADER_TTL)

        threading.Thread(target=_beat, daemon=True).start()

    def stop_lock_heartbeat(self) -> None:
        if self._heartbeat_stop:
            self._heartbeat_stop.set()

    # ------------------------------------------------------------------
    # Shared state: runtime mode
    # ------------------------------------------------------------------

    def init_runtime_state(self, runtime: float) -> None:
        """Called by the first elected leader in runtime mode."""
        state = {
            "mode": ElectionClient.Mode.RUNTIME.value,
            "start_time": time(),
            "runtime": runtime,
        }

        self._r.set(LEADER_RUNTIME_KEY, json.dumps(state))

    def get_remaining_runtime(self) -> Optional[float]:
        """
        Called by a standby candidate that just won election (in runtime mode).
        Returns:
            float | None: seconds remaining (wrt goal set by user), 0 if the window has passed. None, if key is not set.
        """
        raw = self._r.get(LEADER_RUNTIME_KEY)
        if raw is None:
            return None

        state = json.loads(raw)
        elapsed = time() - state["start_time"]
        remaining = state["runtime"] - elapsed

        return max(0.0, remaining)

    # ------------------------------------------------------------------
    # Shared state: num_tasks mode
    # ------------------------------------------------------------------

    def init_task_counter(self, num_tasks: int) -> None:
        """Called by the first elected leader (in num_tasks mode)."""
        # ATMOIC integer counter: using DECR operation
        self._r.set(TASKS_REMAINING_KEY, num_tasks)

    def decrement_tasks_remaining(self) -> int:
        """
        Atomically decrement the task counter (using atomic redis op: DECR) and return the new value.
        Returns:
            int: the value after decrement (negative means overshoot, should stop generating tasks)
        """
        return self._r.decr(TASKS_REMAINING_KEY)

    def increment_tasks_remaining(self) -> None:
        """
        Used to undo an overshoot decrement. Called when decrement returns < 0.
        Args:
            int: the value after increment.
        """
        return self._r.incr(TASKS_REMAINING_KEY)

    def get_tasks_remaining(self) -> int | None:
        """
        Called by a standby candidate that just won election (in runtime mode).
        Returns:
            int | None: number of tasks remaining (wrt the goal set by user), None if key not set
        """
        val = self._r.get(TASKS_REMAINING_KEY)
        if val is None:
            return None

        remaining = int(val)
        return remaining
    
    
    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Delete all election and leader state keys"""
        self._r.delete(LEADER_LOCK_KEY, LEADER_RUNTIME_KEY,
                       TASKS_REMAINING_KEY)
