# Distributed Task Processing System

## Overview

A fault-tolerant distributed task processing system built using Redis, designed to simulate real-world worker orchestration under failures.

The system demonstrates:
- Distributed producer-consumer architecture
- Leader election with failover
- Worker crash recovery
- Task durability via heartbeat + watchdog monitoring
- Process supervision to maintain system liveness

---

## Architecture

### Leader (Producer)
- Multiple leader *candidates* compete for a Redis-based lock
- Exactly one leader is active at a time
- Generates tasks continuously (runtime mode) or up to a fixed count (num_tasks mode)
- Automatically fails over if the active leader crashes

---

### Worker (Consumer)
- Independent OS processes consuming tasks from Redis
- Execute tasks and periodically heartbeat to signal liveness
- Exit automatically after prolonged inactivity
- Restarted by supervisor if they crash

---

### Watchdog (Failure Detector)
- Monitors in-flight tasks via Redis keys with TTL
- Detects tasks whose workers have crashed (no heartbeat)
- Re-queues such tasks for retry

---

### Supervisor (Process Manager)
- Background thread monitoring all workers and leader candidates
- Restarts processes that crash unexpectedly
- Ensures eventual availability of:
  - at least one leader
  - sufficient workers

---

### Task Queue (Redis)
- Central coordination layer
- Uses:
  - `LPUSH` → enqueue tasks
  - `BRPOP` → blocking dequeue
- Tracks in-progress tasks via TTL-based keys

---

## Execution Flow

1. System initializes and clears previous state
2. Workers start and wait on Redis queue
3. Leader candidates start and compete for leadership
4. Elected leader begins generating tasks
5. Workers:
   - fetch tasks
   - register processing state (with TTL)
   - heartbeat during execution
6. If a worker crashes:
   - its task TTL expires
   - watchdog detects and re-queues task
7. Supervisor:
   - detects crashed processes
   - restarts them
8. System shuts down after:
   - leader finishes generation
   - all tasks are processed
   - workers exit after idle cycles

---

## Modes of Operation

### Runtime Mode
- Leader generates tasks for a fixed duration
- Failover leaders continue remaining time

### Num Tasks Mode
- Leader generates a fixed number of tasks
- Counter stored in Redis ensures consistency across failovers

---

## Key Design Concepts

- **Leader Election**
  - Redis `SET NX EX` used for distributed locking
  - TTL + heartbeat ensures automatic failover

- **Heartbeat-Based Liveness**
  - Workers renew task TTL periodically
  - Absence of heartbeat implies failure

- **Failure Recovery**
  - Watchdog re-queues abandoned tasks
  - Supervisor restarts crashed processes

- **Decoupled Architecture**
  - Producers and consumers communicate only via Redis
  - No direct process dependencies

---

## Known Limitations

- **At-least-once execution**
  - Tasks may be executed more than once in rare race conditions

- **Non-atomic dequeue + register**
  - A crash between `BRPOP` and processing registration may lead to task loss  
  - Production systems typically use `BRPOPLPUSH` or Redis Streams to avoid this

- **No idempotency guarantees**
  - Tasks are assumed to be safe for retry

- **Single Redis instance**
  - No replication or clustering

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
python main.py --mode runtime --runtime 30 --num_workers 4 --num_leaders 2
```

or

```bash
python main.py --mode num_tasks --num_tasks 20 --num_workers 4 --num_leaders 2
```

---

## Tech Stack

- Python (multiprocessing, threading)
- Redis (queue + coordination)
- JSON (task serialization)

---

## What This Demonstrates

- Distributed coordination using external state (Redis)
- Leader election with failover
- Fault-tolerant task execution
- Process supervision and recovery
- Realistic failure simulation (random crashes)

---
