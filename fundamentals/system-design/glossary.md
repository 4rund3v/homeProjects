# Glossary

- **Availability** — probability a request receives a valid response within the contract.
- **Back-pressure** — a signal that makes producers slow or shed work when consumers cannot keep up.
- **Consistency** — rules describing which writes a read may observe.
- **Idempotency** — repeating an operation produces the same business result.
- **Invariant** — condition that must remain true across valid state transitions.
- **Linearizability** — each operation appears to take effect at one instant between invocation and response.
- **Partition** — communication failure that divides processes that may still run.
- **Quorum** — enough replicas participating to satisfy a read or write rule.
- **Saturation** — point where added load causes disproportionate queueing or latency.
- **Tail latency** — high percentile latency, commonly p95, p99, or p999.
- **Throughput** — completed work per unit time.
- **Write-ahead log** — durable ordered record written before applying state changes.
