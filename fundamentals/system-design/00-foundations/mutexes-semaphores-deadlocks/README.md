# Mutexes, semaphores, and deadlocks

[Back](../../README.md)

## Why

Mutexes and semaphores are the primitives that turn a read-modify-write into a critical section. They are also the source of the hardest concurrency bugs: deadlocks, priority inversion, and starved threads.

A senior engineer must know when to reach for each and how to keep both from turning latency into an outage.

## How

### Mutex

Exactly one thread may hold the lock at a time. Use it to guard a multi-step critical section.

```text
lock(mutex)
shared_state = read(shared_state)
shared_state = apply(shared_state, op)
write(shared_state)
unlock(mutex)
```

The locked section must be short, must not call untrusted or slow code, and must always release the lock.

### Semaphore

N permits at a time. Use it to bound concurrency on external resources.

```text
acquire(n)
do work
release(n)
```

A binary semaphore is equivalent to a mutex but without ownership semantics. Use a semaphore for "limit how many at once," not for "only one thread reads this field."

### Lock ordering

Every thread that takes multiple locks must do so in the same global order. That order is the deadlock-avoidance invariant.

## Under the hood

A mutex is a kernel or runtime synchronization object. A blocked thread is parked on the kernel's wait queue. On release, one waiting thread is woken. The wake order can be LIFO, FIFO, or priority-based depending on the OS.

Semaphores add a count. The acquire path is either take a permit or park the thread.

Deadlock requires all four conditions:

1. Mutual exclusion
2. Hold-and-wait
3. No preemption
4. Circular wait

Breaking any one condition prevents the deadlock. The practical choices are to fix the lock order, to time out the acquire, or to use a transaction manager that enforces one ordering.

### Priority inversion

A low-priority thread holds the lock; a high-priority thread wants it; a medium-priority thread preempts the low-priority holder. The high-priority thread is now blocked behind the medium-priority thread. Fix: priority-inheritance mutex, or restructure the work.

## Production use cases

- Database connection pool with a semaphore bound.
- Cache miss handling with a single-flight mutex on the key.
- Job scheduler that must serialize state transitions per key.
- File-system lock in a worker.

## Trade-offs and failure modes

| Choice | Gains | Costs | Failure to watch |
|---|---|---|---|
| Mutex | simple, strong guarantee | blocks, can deadlock | hold time, lock ordering |
| Semaphore | bounded concurrency | permits leak on early return | try/finally release |
| Atomic CAS | lock-free, no blocking | ABA, retry storm | CAS loop spin |
| read-write lock | many readers | reader starvation, false sharing | write path held too long |

## Observability

- Mutex wait p50/p95/p99 and max.
- Semaphore saturation: `permits == 0` fraction of time.
- Lock-hold-time histogram.
- Deadlock detector: dump stack traces of all threads that are blocked on a lock.

## Lab

Build a worker pool with a semaphore that limits concurrency to 4. Watch acquire time under saturation. Then add two locks and a wrong-order acquire to reproduce a deadlock; remove it by fixing the order.

## Worked examples

**Situation: DB connection pool of 50, 200 concurrent goroutines.**
Throughput ceiling = 50 permits / 20 ms avg hold = 2,500 transactions/second. With 200 goroutines all waiting, queue depth = 200. Little's law: average wait = queue / throughput = 200 / 2,500 = 80 ms. The p99 transaction latency is 20 ms (work) + 80 ms (wait) = 100 ms. If the SLO is p99 < 50 ms, the pool is undersized. Increase to 100 permits → wait = 100/5,000 = 20 ms → p99 = 40 ms, inside SLO.

Deadlock: two locks, two transactions. T1 holds C, wants I. T2 holds I, wants C. No progress. Deadlock detector fires at 30 s (max configured wait), kills T1. T2 proceeds. The kill cost is 1 aborted transaction per 30 s window — negligible at 2,500 tps.

```text
T1: lock(C) → wait lock(I)
T2: lock(I) → wait lock(C)
cycle → kill T1 → T2 proceeds
```

## How to use this topic

Use the sequence: [basics](basics.md) for the worked example, [information](information.md) for production reference, and [mechanism lesson](learn/01-mechanism.md) for a guided exercise. Every design decision should trace back to the invariant and a measured failure mode.
