# Stream Analyzer

**Goal:** Build a real-time telemetry and access log window analyzer CLI in Go that detects anomalies, tracks streaming percentiles, and correlates asynchronous events using sliding windows, monotonic queues/stacks, two pointers, two-heap priority queues, and Fenwick trees.

**Scope:** JSON and access log parsing, fixed-window rolling throughput and error rate, monotonic deque for $O(1)$ sliding window maximum latency, monotonic stack for next greater latency spike detection, variable-window minimum slice containing targeted error sequences, two-pointer chronological request-response correlation, two-heap streaming running median, bounded top-K slowest endpoints, and Fenwick tree (Binary Indexed Tree) for dynamic range metric queries.

**Out of scope:** Distributed stream processing (Flink/Kafka Streams), persistent time-series database storage, web dashboard, alerting notification backends (PagerDuty/Slack).

**Learning focus:** Sliding window invariant maintenance (shrinking left pointer while maintaining window criteria, expanding right pointer); monotonic deque for instant window maximums; monotonic stack for nearest greater element; two-pointer convergence proof and memory efficiency; two-heap pattern for exact running median latency ($O(\log N)$ ingest, $O(1)$ query); Fenwick tree (Binary Indexed Tree) for $O(\log N)$ dynamic prefix and range metric sums; streaming one-pass vs. batch offline algorithms.

**Depends on:** [`go-fundamentals`](../go-fundamentals/README.md)

## Milestones
- [ ] Milestone 1 — Fixed sliding window & Monotonic Deque: rolling W-second window data structure calculating throughput and error rate with $O(1)$ amortized state transitions, plus a monotonic deque tracking the sliding window peak (maximum) latency in $O(1)$ time.
- [ ] Milestone 2 — Variable sliding window & Monotonic Stack: find minimum log time slice containing target sequence of error signatures (Minimum Window Substring pattern), and implement a monotonic stack to compute the next higher latency spike and spike duration for every event.
- [ ] Milestone 3 — Two-pointer stream correlation: timestamp-ordered reconciliation between request and response streams with bounded time skew and pair latency SLO verification.
- [ ] Milestone 4 — Two-heap running median, Top-K, & Fenwick Range Index: dual-heap running median ($O(\log N)$ update, $O(1)$ query); bounded min-heap for Top-K slowest endpoints; Fenwick tree (Binary Indexed Tree) for dynamic time-range metric aggregation in $O(\log N)$.
