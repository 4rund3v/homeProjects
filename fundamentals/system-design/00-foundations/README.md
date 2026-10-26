# Foundations

Foundations make correctness explicit before distribution makes it difficult. Study concurrency first: a transaction is a controlled state transition, and a lock is only one way to coordinate competing transitions.

## Route

1. [Concurrency fundamentals](concurrency-fundamentals/README.md)
2. [Race conditions](race-conditions/README.md)
3. [Mutexes, semaphores, and deadlocks](mutexes-semaphores-deadlocks/README.md)
4. [Distributed locks](distributed-locks/README.md)
5. [Transactions](transactions/README.md)
6. [Database transactions](database-transactions/README.md)
7. [Isolation levels](database-isolation-levels/README.md)
8. [Database locking](database-locking/README.md)
9. [Pessimistic locking](pessimistic-locking/README.md)
10. [Optimistic locking](optimistic-locking/README.md)
11. [Flash-sale inventory](flash-sale-inventory/README.md)

## Core invariant

For a stock counter, never allow committed inventory below zero. Every later technique is judged against this invariant under concurrent requests, retries, crashes, and failover.
