# Distributed Worker System (v1 - Simulation)

## Overview

> This is v1 of a multi-stage project evolving into a fully distributed system.

This project is a simulation of a distributed worker system, designed to demonstrate core concepts such as task scheduling, worker coordination, and concurrent execution.

In this version (v1), the system runs within a single process but models how a leader assigns tasks to multiple workers, which process them concurrently using threads.

---

## Architecture

The system consists of three main components:

### Leader
- Maintains a queue of tasks
- Tracks available workers
- Assigns tasks to idle workers

### Worker
- Represents an execution unit
- Processes tasks in a separate thread
- Transitions between `IDLE` and `ACTIVE` states

### Task
- Represents a unit of work
- Moves through states:
  - `PENDING → IN_PROGRESS → DONE`

---

## Execution Flow

1. Tasks are created and added to the leader's queue
2. The leader continuously:
   - finds an idle worker
   - assigns a task
3. Workers process tasks concurrently using threads
4. Once completed:
   - worker becomes idle
   - task is marked as done
5. Leader waits for all tasks to finish before exiting

---

## How to Run

```bash
python main.py --num_workers=4 --num_tasks=10
```

---

## Sample Output

```bash
(12) Starting Processing: 10 tasks: 4 workers ...
(12) Leader assigning Task 1 to Worker A
(12) Worker A: Task 1: Starting processing
(12) Leader assigning Task 2 to Worker B
(12) Worker B: Task 2: Starting processing
...
(15) Worker A: Task 1: Completed
(15) Worker A is now IDLE
...
(18) Finished Processing ...
```

---

## Key Concepts Demonstrated
- Centralized task scheduling
- Worker pool model
- Concurrent task execution using threads
- Basic task lifecycle management
- State-based worker availability

---

## Limitations (v1)
- Runs in a single process (not truly distributed)
- Leader directly assigns tasks (push-based model)
- No fault tolerance (worker/leader crashes not handled)
- No shared state across processes
- No load balancing beyond simple availability check

---

## Future Improvements
- Introduce shared queue using Redis
- Transition to pull-based worker model
- Implement leader election
- Add failure handling and task reassignment
- Introduce rate limiting and system metrics

---

## Tech Stack
- Python
- threading (for concurrency)

---