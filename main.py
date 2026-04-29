import argparse
import multiprocessing
import time

from task import Task
from worker import Worker
from leader import Leader
from infra.task_queue import TaskQueue

HOST = "127.0.0.1"
PORT = 6379


parser = argparse.ArgumentParser()
parser.add_argument('--num_workers', type=int, default=4)
parser.add_argument('--num_tasks', type=int, default=10)


def process(num_workers: int, num_tasks: int):
    if num_workers > 10:
        print("Max number of workers allowed is 10")
        return

    # Clear any leftover tasks from earlier runs
    TaskQueue(host=HOST, port=PORT).clear()

    # Start the workers, they wait until tasks are pushed into queue by leader, then consume
    workers = [Worker(worker_id=chr(i + ord('A')), host=HOST, port=PORT)
               for i in range(num_workers)]
    for worker in workers:
        worker.start()

    tasks = [Task(i + 1) for i in range(num_tasks)]
    leader = Leader(tasks=tasks, host=HOST, port=PORT)

    start = time.perf_counter()
    leader.run()

    for worker in workers:
        worker.join()

    elapsed = time.perf_counter() - start
    print(f"Total time: {elapsed:.2f}s")


if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    args = parser.parse_args()
    process(**vars(args))
