# System Design — Deep Dives

> The companion folder to the overview in [`../system-design.md`](../system-design.md).
> The overview names the trade-off dials. This folder goes deep on each dimension, with
> worked examples and the exact numbers/intuitions an L5/L6 interview wants.

## The files

| File | Covers |
|------|--------|
| [`scalability.md`](scalability.md) | Vertical vs horizontal, the bottlenecks *here*, and how each axis scales |
| [`reliability.md`](reliability.md) | Failure taxonomy, MTBF/MTTR, RPO/RTO, and the "make failures cheap" principle |
| [`consistency.md`](consistency.md) | The consistency model spectrum, CAP/PACELC done right, and where this system sits |
| [`latency-throughput.md`](latency-throughput.md) | Latency budgets, percentiles, the latency/throughput trade, back-pressure |
| [`design-worksheet.md`](design-worksheet.md) | The actual 30-minute "design a system" worksheet, applied to this project |

## How to use it

- **Before the interview:** work [`design-worksheet.md`](design-worksheet.md) out loud
  on this system, then abstract it to "design a URL shortener" or "design a
  notification service." The worksheet is the reusable skill.
- **For a specific question** (scalability / consistency / availability): go straight
  to that file.
- **The numbers that matter** (RPO, p99, partition counts) are called out with the
  *reasoning*, not just the value.

Cross-references: the concrete system in [`../architecture.md`](../architecture.md);
the patterns that make it resilient in [`../architecture-patterns/`](../architecture-patterns/);
the OOP/domain decomposition in [`../domain-decomposition.md`](../domain-decomposition.md).
