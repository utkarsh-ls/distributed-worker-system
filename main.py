import argparse
import time

from task import Task
from worker import Worker
from leader import Leader


parser = argparse.ArgumentParser()
parser.add_argument('--num_workers', type=int, default=4)
parser.add_argument('--num_tasks', type=int, default=10)

start = time.perf_counter()


def process(num_workers: int, num_tasks: int):
    if num_workers>10:
        print(f"Max number of workers allowed are 10")
        return

    tasks = [Task(i+1) for i in range(num_tasks)]
    workers = [Worker(chr(i+ord('A'))) for i in range(num_workers)]
    leader = Leader(tasks = tasks, workers = workers)
    
    leader.run()


if __name__ == '__main__':
    args = parser.parse_args()
    process(**vars(args))
