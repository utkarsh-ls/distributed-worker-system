import argparse
import multiprocessing
import threading
import os
import random
import signal
from time import sleep, perf_counter

from task import Task
from worker import Worker
from leader import Leader
from infra.task_queue import TaskQueue
from infra.watchdog import Watchdog
from infra.config import REDIS_HOST, REDIS_PORT


parser = argparse.ArgumentParser()
parser.add_argument('--num_workers', type=int, default=4)
parser.add_argument('--num_tasks', type=int, default=10)
parser.add_argument('--crash_workers', type=int, default=1, help="Number of workers to crash during execution (default: 1)")


def crash_simulator(workers: list[Worker], num_crashes: int):
    """
    Background thread: Crashes up to `num_crashes` random active workers
    
    Waits a short random delay before each kil to ensure workers have had time to pick tasks and are mid-execution.
    """
    crashes_done = 0
    while crashes_done < num_crashes:
        # Wait for workers to start processing tasks
        delay = random.uniform(1.0, 2.5)
        sleep(delay)
        active = [w for w in workers if w.is_alive() and w.state==Worker.State.ACTIVE]
        # No active workers right now, wait and retry
        if not active:
            continue
        
        target = random.choice(active)
        print(f"({int(perf_counter())%100:02d}) CRASH SIMULATOR: Killing worker {target.worker_id} (pid={target.pid})")
        os.kill(target.pid, signal.SIGKILL)
        crashes_done += 1

def process(num_workers: int, num_tasks: int, crash_workers: int):
    if num_workers > 10:
        print("Max number of workers allowed is 10")
        return
    if num_workers <= crash_workers:
        print("Please ensure there are more workers than number of crashes.")

    # Clear any leftover tasks from earlier runs
    TaskQueue(host=REDIS_HOST, port=REDIS_PORT).clear()
    
    # Start the watchdog (monitor task completion, manages recovery in case of worker crash)
    watchdog = Watchdog(host=REDIS_HOST, port=REDIS_PORT)
    watchdog.start()

    # Start the workers, they wait until tasks are pushed into queue by leader, then consume
    workers = [Worker(worker_id=chr(i + ord('A')), host=REDIS_HOST, port=REDIS_PORT)
               for i in range(num_workers)]
    for worker in workers:
        worker.start()

    # Start the crash simulator in a background thread
    if crash_workers > 0:
        crash_thread = threading.Thread(
            target=crash_simulator,
            args=(workers, crash_workers),
            daemon=True
        )
        crash_thread.start()

    # Leader pushes the tasks into waiting queue
    tasks = [Task(id=i+1, payload={"job": f"task_{i+1}"}) for i in range(num_tasks)]
    leader = Leader(tasks=tasks, host=REDIS_HOST, port=REDIS_PORT)

    start = perf_counter()
    leader.run()

    # Wait for workers to finish
    for worker in workers:
        worker.join()

    elapsed = perf_counter() - start
    print(f"Total time: {elapsed:.2f}s")
    
    # Stop watchdog
    watchdog.stop()
    watchdog.join(timeout=5)


if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    args = parser.parse_args()
    process(**vars(args))
