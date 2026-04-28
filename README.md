# Distributed Worker System (v2 - Multi-Process Queue)

## Overview

> This is v2 of a multi-stage project evolving into a fully distributed system.

This version transitions from a simulated, thread-based system to a **multi-process architecture** where workers operate as independent OS processes and communicate via a shared task queue.

The system now follows a **pull-based model**, where workers fetch tasks independently rather than being assigned work directly by the leader.

---

## Architecture

### Leader
- Starts and manages worker processes
- Enqueues tasks into a shared queue
- Signals workers to shut down after tasks are complete

### Worker (Process)
- Runs as an independent OS process
- Continuously pulls tasks from the shared queue (blocking)
- Processes tasks and updates internal state
- Shuts down gracefully upon receiving a sentinel signal

### Task
- Represents a unit of work
- Moves through states:
  - `PENDING → IN_PROGRESS → DONE`

### Shared Queue
- Implemented using `multiprocessing.Queue`
- Acts as the central coordination mechanism
- Enables decoupling between leader and workers

---

## Execution Flow

1. Leader initializes workers and starts processes
2. Leader enqueues all tasks into the shared queue
3. Workers:
   - block on queue (`get()`)
   - pick tasks as they become available
   - process tasks independently
4. Leader sends sentinel values (`None`) to signal shutdown
5. Workers exit gracefully after completing assigned work
6. Leader waits for all workers to finish (`join()`)

---

## How to Run

```bash
python main.py --num_workers=4 --num_tasks=10
```

---