# Distributed Worker System (v3 - Redis-Based Distributed Queue)

## Overview

> This is v3 of a multi-stage project evolving into a fully distributed system.

This version introduces a **Redis-backed shared queue**, transitioning the system from local inter-process coordination to a **distributed architecture**.

Workers are now fully independent processes that fetch tasks directly from Redis, enabling decoupling between producers and consumers and mimicking real-world distributed systems.

---

## Architecture

### Leader (Producer)
- Responsible only for creating and enqueueing tasks
- Has no knowledge of workers
- Pushes tasks into Redis queue

### Worker (Consumer)
- Runs as an independent OS process
- Connects directly to Redis
- Continuously pulls tasks using a blocking call
- Processes tasks independently
- Terminates after repeated idle cycles (no tasks available)

### Task
- Represents a unit of work
- Serialized to JSON for transport
- Moves through states:
  - `PENDING → IN_PROGRESS → DONE`

### Shared Queue (Redis)
- Implemented using Redis Lists
- Uses:
  - `LPUSH` → enqueue
  - `BRPOP` → blocking dequeue
- Acts as the central coordination layer across processes

---

## Execution Flow

1. Workers start and connect to Redis
2. Workers block on the queue (`BRPOP`) waiting for tasks
3. Leader pushes tasks into the queue (`LPUSH`)
4. Workers:
   - fetch tasks as they become available
   - process them independently
5. If no tasks are received for several cycles:
   - workers shut down automatically
6. Main process waits for all workers to exit

---

## How to Run

### 1. Start Redis locally

```bash
redis-server
```
### 2. Run the system

```bash
python main.py --num_workers=4 --num_tasks=10
```

---

## Key Concepts Demonstrated

- Distributed task queue using Redis
- Producer-consumer architecture
- Pull-based worker model
- Inter-process communication via external system
- Blocking queue consumption (`BRPOP`)
- Task serialization (JSON encoding/decoding)
- Decoupled system components

---

## Improvements Over v2

| Feature | v2 | v3 |
|--|--|--|
| Queue type | multiprocessing.Queue | Redis |
| Scope | Single machine | Distributed-ready |
| Worker model | Semi-coupled | Fully decoupled |
| Communication | Shared memory | Networked |
| Task transfer | In-memory objects | Serialized (JSON) |

---

## Limitations (v3)

- No task reliability (task loss possible if worker crashes)
- No acknowledgment or retry mechanism
- No worker heartbeat or monitoring
- No leader election
- No rate limiting or backpressure
- Single queue (no prioritization or partitioning)

---

## Future Improvements

- Implement reliable queue pattern using Redis (e.g., processing queue)
- Add task acknowledgment and retry logic
- Introduce worker failure detection
- Implement leader election for high availability
- Add rate limiting and metrics (e.g., latency, throughput)
- Support multiple queues / priority queues

---

## Tech Stack

- Python
- multiprocessing (process-based execution)
- Redis (distributed queue and coordination layer)

---