from time import perf_counter

from task import Task
from infra.task_queue import TaskQueue


class Leader:
    """
    The Leader pushes tasks into the queue. No knowledge of workers (akin to a producer).
    """

    def __init__(self, tasks: list[Task], host: str = "127.0.0.1", port: int = 6379):
        self.tasks = tasks
        self.queue = TaskQueue(host, port)

    def run(self):
        num_tasks = len(self.tasks)
        print(f"({int(perf_counter())%100:02d}) Leader: starting {num_tasks} tasks, queue size {self.queue.depth()}")

        for task in self.tasks:
            qsize = self.queue.push(task)
            print(f"({int(perf_counter())%100:02d}) Leader: Enqueued Task {task.id}, Queue size {qsize}")

        print(f"({int(perf_counter())%100:02d}) Leader: All tasks enqueued")
