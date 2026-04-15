from queue import Queue
from time import sleep, perf_counter

from task import Task
from worker import Worker


class Leader:
    def __init__(self, tasks: list[Task], workers: list[Worker]):
        self.tasks = Queue()
        [self.tasks.put(task) for task in tasks]
        self.workers = workers

    def find_next_worker(self):
        idle_worker = next(filter(lambda worker: worker.state ==
                           Worker.State.IDLE, self.workers), None)
        return idle_worker

    def run(self):
        print(f"({int(perf_counter())%100}) Starting Processing: {self.tasks.qsize()} tasks: {len(self.workers)} workers ...")

        running_processes = []
        while not self.tasks.empty():
            idle_worker = self.find_next_worker()
            while idle_worker is None:
                sleep(0.5)
                idle_worker = self.find_next_worker()
            task = self.tasks.get_nowait()

            print(f"({int(perf_counter())%100}) Leader assigning Task {task.id} to Worker {idle_worker.id}")
            running_processes.append(idle_worker.process(task))

        # Wait for all the tasks to finish executing
        for rp in running_processes:
            rp.join()

        print(f"({int(perf_counter())%100}) Finished Processing ...")
