import argparse
import multiprocessing
import time
 
from task import Task
from worker import Worker
from leader import Leader
 
 
parser = argparse.ArgumentParser()
parser.add_argument('--num_workers', type=int, default=4)
parser.add_argument('--num_tasks', type=int, default=10)
 
 
def process(num_workers: int, num_tasks: int):
    if num_workers > 10:
        print("Max number of workers allowed is 10")
        return
 
    # A Distributed task queue, common for all workers
    task_queue = multiprocessing.Queue()
 
    tasks = [Task(i + 1) for i in range(num_tasks)]
    workers = [Worker(worker_id=chr(i + ord('A')), task_queue=task_queue)
               for i in range(num_workers)]
 
    leader = Leader(tasks=tasks, workers=workers)
 
    start = time.perf_counter()
    leader.run()
    elapsed = time.perf_counter() - start
    print(f"Total time: {elapsed:.2f}s")
 
 
if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    args = parser.parse_args()
    process(**vars(args))