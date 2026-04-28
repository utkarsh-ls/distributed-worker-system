import multiprocessing
from time import perf_counter

from task import Task
from worker import Worker


class Leader:
    """
    The Leader owns the shared task queue and a pool of Worker processes.
    """
    
    def __init__(self, tasks: list[Task], workers: list[Worker]):
        self.tasks = tasks
        self.workers = workers

    def run(self):
        num_tasks = len(self.tasks)
        num_workers = len(self.workers)
        print(f"({int(perf_counter())%100:02d}) Leader: starting - {num_tasks} tasks: {num_workers} workers")

        # Step 1: Start all worker processes
        for worker in self.workers:
            worker.start()
            
        # Step 2: Enqueue all tasks
        # All workers share the same task queue
        for task in self.tasks:
            self.workers[0].task_queue.put(task)

        # Step 3: Send one sentinel (None) per worker to signal shutdown
        for _ in self.workers:
            self.workers[0].task_queue.put(None)
        
        # Step 4: Wait for all workers to finish
        for worker in self.workers:
            worker.join()
        
        print(f"({int(perf_counter())%100}) Leader: All tasks complete")
