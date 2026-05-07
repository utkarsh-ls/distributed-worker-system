import argparse
import multiprocessing
import threading
import os
import shutil
import random
import signal
from time import sleep, perf_counter

# Clear any metric data from earlier runs (before infra.metrics import, or counters will get deleted)
from infra.config import PROMETHEUS_MULTIPROC_DIR
shutil.rmtree(PROMETHEUS_MULTIPROC_DIR, ignore_errors=True)
os.makedirs(PROMETHEUS_MULTIPROC_DIR, exist_ok=True)

from infra.logger import logger
from infra.metrics import start_metrics_server
from worker import Worker
from leader import Leader
from infra.task_queue import TaskQueue
from infra.election import ElectionClient
from infra.watchdog import Watchdog
from infra.supervisor import Supervisor
from infra.config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, METRICS_PORT,
    CRASH_PROBABILITY, CRASH_CHECK_INTERVAL,
)

parser = argparse.ArgumentParser()
parser.add_argument(
    '--mode', choices=["runtime", "num_tasks"], default="runtime")
parser.add_argument('--runtime', type=float, default=30,
                    help="Seconds to generate tasks (runtime mode)")
parser.add_argument('--num_tasks', type=int, default=10,
                    help="Total tasks to generate (num_tasks mode)")
parser.add_argument('--num_leaders', type=int, default=2,
                    help="Number of leader candidates")
parser.add_argument('--num_workers', type=int, default=4,
                    help="Number of worker processes")
parser.add_argument('--crash_prob', type=float, default=CRASH_PROBABILITY,
                    help="Per-process crash probability per check interval (0 to disable)")


# ------------------------------------------------------------------
# Crash Simulator
# ------------------------------------------------------------------

def _process_label(proc) -> str:
    """
    Return a human-readable label for a process.
    Leader has candidate_id, Worker has worker_id
    """
    if isinstance(proc, Leader):
        return f"Leader {proc.candidate_id}"
    if isinstance(proc, Worker):
        return f"Worker {proc.worker_id}"
    return proc.name


def crash_simulator(processes: list[multiprocessing.Process], crash_prob: float):
    """
    Background thread. Every CRASH_CHECK_INTERVAL seconds, each alive process independently rolls against crash_prob.
    If it hits, its terminated.

    Allows for multiple processes crashing simultaneously (eg: leader and worker crash together).

    Args:
        processes (list[Process]): a flat list of all crashable processes (leaders + workers).
    """
    while True:
        sleep(CRASH_CHECK_INTERVAL)
        for proc in list(processes):
            if not proc.is_alive():
                continue
            if random.random() < crash_prob:
                label = _process_label(proc)
                logger.error(f"CRASH SIMULATOR: Killing {label} (pid={proc.pid})")

                try:
                    os.kill(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass    # already dead, ignore


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def process(mode: str, runtime: float, num_tasks: int, num_leaders: int, num_workers: int, crash_prob: float):
    if num_workers > 10:
        logger.warning("Max number of workers allowed is 10")
        return
    if num_leaders > 5:
        logger.warning("Max number of leader candidates allowed is 5")
        return

    # Clear all Redis state from earlier runs
    TaskQueue(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB).clear()
    ElectionClient("_init", host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB).clear()
    
    # Start metrics server
    metrics_server = start_metrics_server(METRICS_PORT)

    # 1. Start the watchdog (monitor task completion, manages recovery in case of worker crash)
    watchdog = Watchdog(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    watchdog.start()

    # 2. Start the workers, they wait until tasks are pushed into queue by leader, then consume
    workers = [
        Worker(
            worker_id=chr(i + ord('A')),
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
        )
        for i in range(num_workers)
    ]
    for worker in workers:
        worker.start()

    # 3. Start leader candidates
    leaders = [
        Leader(
            candidate_id=f"L{i+1}", mode=mode, runtime=runtime,
            num_tasks=num_tasks, host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
        )
        for i in range(num_leaders)
    ]
    for leader in leaders:
        leader.start()

    # 4. Start supervisor
    supervisor = Supervisor(
        leaders=leaders, workers=workers, mode=mode, runtime=runtime,
        num_tasks=num_tasks, host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
    )
    supervisor.start()

    # 5. Start the crash simulator in a background thread
    if crash_prob > 0:
        threading.Thread(
            target=crash_simulator,
            args=(leaders+workers, crash_prob),
            daemon=True,
            name="Crash Simulator",
        ).start()

    start = perf_counter()

    # 6. Wait for supervisor to exit. Supervisor handles the leader/worker lifecycle (respawn+join)
    supervisor.join()

    elapsed = perf_counter() - start
    logger.info(f"Total time: {elapsed:.2f}s")

    # Stop watchdog, metrics server
    watchdog.stop()
    watchdog.join(timeout=5)
    metrics_server.join(timeout=5)


if __name__ == '__main__':
    if multiprocessing.get_start_method(allow_none=True) is None:
        multiprocessing.set_start_method('spawn')
    
    args = parser.parse_args()
    process(**vars(args))
