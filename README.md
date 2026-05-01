# Distributed Worker System (v4 - Fault-Tolerant Execution with Recovery)

## Overview

> This is v4 of a multi-stage project evolving into a fully distributed system.

This version introduces **fault tolerance and task recovery**, transforming the system into a **reliable distributed task processor**.

Workers can now crash during execution, and tasks are automatically recovered and reprocessed using a **heartbeat + watchdog mechanism**.

---

## Architecture

### Leader (Producer)
- Pushes tasks into Redis queue
- Has no knowledge of workers
- Does not participate in task execution or recovery

### Worker (Consumer)
- Runs as an independent OS process
- Pulls tasks from Redis (`BRPOP`)
- Registers task as "in-progress" with TTL
- Sends periodic heartbeats to maintain ownership
- Acknowledges task completion
- Can crash mid-execution (simulated)

### Watchdog (Recovery Process)
- Independent process monitoring task execution
- Scans for tasks nearing TTL expiry
- Re-queues tasks whose workers likely crashed

### Task
- Represents a unit of work
- Serialized to JSON
- Moves through states:
  - `PENDING → IN_PROGRESS → DONE`

---

## Redis Data Model

### Main Queue
- Key: `task_queue`
- Type: List
- Operations:
  - `LPUSH` → enqueue
  - `BRPOP` → dequeue

### Processing Keys
- Key: `processing:{task_id}`
- Type: String (serialized task)
- TTL-based ownership tracking

---

## Execution Flow

1. Workers start and block on queue (`BRPOP`)
2. Leader enqueues tasks into Redis
3. Worker:
   - pops task
   - registers processing key with TTL
   - starts heartbeat loop
4. Worker executes task
5. On success:
   - worker acknowledges task (deletes processing key)
6. If worker crashes:
   - heartbeat stops
   - TTL expires
7. Watchdog:
   - detects expiring tasks
   - requeues them

---

## Failure Handling Model

### Heartbeat Mechanism
- Workers periodically renew TTL on processing keys
- Ensures active tasks are not reclaimed

### Watchdog Recovery
- Scans processing keys
- Requeues tasks nearing expiry

### Crash Simulation
- Random worker processes are killed using `SIGKILL`
- Recovery is verified through task re-execution

---

## Important Design Notes

### Task Status in Redis

> Task status stored in Redis is **not authoritative**.

- It is not used for scheduling
- It exists only for reconstruction during recovery
- Actual execution state is derived from:
  - queue presence
  - processing key existence

---

### Delivery Semantics

This system provides:

- **At-least-once execution**

This means:
- Tasks may execute more than once in rare edge cases
- No task is permanently lost

---

### Timing Guarantees

To avoid false recovery:

```
PROCESSING_TTL - HEARTBEAT_INTERVAL > EXPIRY_CHECK_THRESHOLD
```

This ensures:
- Active tasks are not mistakenly requeued
- Expired tasks are reliably detected

---

## How to Run

### 1. Start Redis

This system requires a running Redis instance.

#### Option 1: Run Redis with Docker (Recommended)

```bash
docker run -d \
  --name redis-server \
  -p 6379:6379 \
  redis:7
```

This will:
- start a Redis container
- expose it on `localhost:6379`

---

#### Option 2: Run Redis Locally

If Redis is installed on your system:

```bash
redis-server
```

---

#### Configuration

Redis connection settings are defined in:

```
infra/config.py
```

```python
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
```

Update these values if:
- Redis is running on a different host
- You are using a different port
- You are connecting to a remote server or container network

---

#### Notes

- If Redis is running directly on your machine (`redis-server`):
  - use `127.0.0.1` (or `localhost`) as host

- If Redis is running in Docker with port mapping (`-p 6379:6379`):
  - use `127.0.0.1` (or `localhost`) as host

- If both your app and Redis are running inside Docker on the same network:
  - use the container name as host (e.g., `redis-server`)

---

### 2. Run the system

```bash
python main.py --num_workers=4 --num_tasks=10 --crash_workers=2
```

Simulates worker failures to test recovery.

---

## Key Concepts Demonstrated

- Distributed task queue (Redis)
- Producer-consumer architecture
- Fault-tolerant processing
- Heartbeat-based liveness detection
- TTL-based coordination
- Watchdog recovery pattern
- At-least-once delivery semantics
- Failure simulation and validation

---

## Improvements Over v3

| Feature | v3 | v4 |
|--|--|--|
| Task reliability | ❌ | ✅ |
| Crash recovery | ❌ | ✅ |
| Heartbeat | ❌ | ✅ |
| Watchdog | ❌ | ✅ |
| Delivery guarantees | None | At-least-once |

---

## Limitations (v4)

- Possible duplicate execution (no deduplication)
- No leader election (single producer)
- No task prioritization
- No observability system (logs only)
- No backpressure handling

---

## Future Improvements

- Leader election (high availability)
- Deduplication / idempotency layer
- Metrics and observability (Grafana, Prometheus)
- Rate limiting and throttling
- Variable task complexity and duration

---

## Tech Stack

- Python
- multiprocessing
- Redis
- threading (heartbeat + crash simulation)

---
