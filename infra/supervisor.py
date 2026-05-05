import threading
from time import sleep

from infra.logger import logger
from worker import Worker
from leader import Leader
from infra.config import SUPERVISOR_INTERVAL


class Supervisor(threading.Thread):
    """
    Monitors worker and leader candidate pools in a background thread.
    Restarts dead processes to maintain original pool sizes (per cycle).
    """

    def __init__(self, workers: list[Worker], leaders: list[Leader], mode: str, runtime: float, num_tasks: int, host: str, port: int, db: int):
        super().__init__(daemon=True, name="Supervisor")
        self._workers = workers
        self._leaders = leaders
        self._mode = mode
        self._runtime = runtime
        self._num_tasks = num_tasks
        self._host = host
        self._port = port
        self._db = db

        self._stop_leaders = threading.Event()
        self._stop_workers = threading.Event()

        # Monotonic counter for unique replacement leader IDs
        self._leader_counter = len(leaders)
    
    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    
    def _next_leader_id(self) -> str:
        self._leader_counter += 1
        return f"L{self._leader_counter}"
    
    
    # ------------------------------------------------------------------
    # Respawm thread targets
    # ------------------------------------------------------------------
    
    def respawn_workers(self) -> None:
        # Respawn dead workers
        while not self._stop_workers.is_set():
            sleep(SUPERVISOR_INTERVAL)

            dead_workers = [w for w in self._workers if not w.is_alive()]
            for dead in dead_workers:
                # Reap exited process before dropping reference (avoid zombies)
                dead.join(timeout=0.1)
                self._workers.remove(dead)
                # If worker exited cleanly, dont spawn replacement
                if dead.clean_exit.is_set():
                    continue
                replacement = Worker(worker_id=dead.worker_id, host=self._host, port=self._port, db=self._db)
                replacement.start()
                self._workers.append(replacement)
                logger.warning(f"Supervisor: restarted Worker {replacement.worker_id} (pid={replacement.pid})")

            # Stop the loop if all workers exit cleanly (=> no workers in list after the respawn loop)
            if not self._workers:
                self._stop_workers.set()
    
    def respawn_leader_candidates(self) -> None:
        # Respawn dead leader candidates
        while not self._stop_leaders.is_set():
            sleep(SUPERVISOR_INTERVAL)

            dead_leaders = [l for l in self._leaders if not l.is_alive()]

            for dead in dead_leaders:
                # Reap exited process before dropping reference (avoid zombies)
                dead.join(timeout=0.1)
                self._leaders.remove(dead)
                # If leader-candidate exited cleanly, dont spawn replacement
                if dead.clean_exit.is_set():
                    continue
                new_id = self._next_leader_id()
                replacement = Leader(
                    candidate_id=new_id, mode=self._mode, runtime=self._runtime,
                    num_tasks=self._num_tasks, host=self._host, port=self._port, db=self._db,
                )
                replacement.start()
                self._leaders.append(replacement)
                logger.warning(f"Supervisor: restarted Leader candidate {new_id} (pid={replacement.pid})")

            # Stop the loop if all leaders exit cleanly (=> no leaders in list after the respawn loop)
            if not self._leaders:
                self._stop_leaders.set()
    
    
    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        logger.info(f"Supervisor: started")

        respawn_threads = [
            # Worker respawn thread
            threading.Thread(
                target=self.respawn_workers,
                daemon=True,
                name="Worker Respawn",
            ),
            # Leader candidate respawn thread
            threading.Thread(
                target=self.respawn_leader_candidates,
                daemon=True,
                name="Leader Respawn",
            )
        ]

        for t in respawn_threads:
            t.start()

        for t in respawn_threads:
            t.join()

        logger.info(f"Supervisor: all processes exited cleanly, shutting down")
