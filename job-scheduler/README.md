# Job Scheduler

**Goal:** Build a cluster task placement and SLA capacity planner CLI in Go that simulates compute cluster job scheduling, resolves overlapping reservations, and sizes worker capacity using interval math, binary search on answer spaces, dynamic programming, and greedy heuristics.

**Scope:** Interval overlap detection and peak concurrency calculation (sweep-line and min-heap), interval coalescing and free window inversion, binary search on capacity answer space with monotonic feasibility predicate, greedy Earliest Deadline First (EDF) and Shortest Job First (SJF) dispatchers with maximum lateness tracking, Weighted Interval Scheduling (1D Dynamic Programming with binary search $O(N \log N)$), 0/1 Knapsack node memory task packing (DP), CLI subcommands (`peak-nodes`, `free-slots`, `size-capacity`, `plan`, `optimal-weighted`, `pack-node`), table-driven unit tests, benchmarks, formal greedy exchange argument documentation.

**Out of scope:** Live Kubernetes/Borg cluster API integrations, distributed consensus or multi-agent cluster RPCs, continuous daemon loops or systemd services, web UI or REST endpoints, dynamic task preemption during execution.

**Learning focus:** Interval sweep-line and min-heap algorithms (Meeting Rooms II pattern), interval coalescing and schedule inversion (Merge Intervals), binary search on answer space (Ship Packages / Capacity Sizing pattern), formulating monotonic feasibility predicates `canCompleteUnderSLA`, greedy scheduling heuristics (EDF, SJF), formal exchange arguments proving greedy optimality, Weighted Interval Scheduling via Dynamic Programming and binary search ($O(N \log N)$), 0/1 Knapsack Dynamic Programming for bounded resource packing, and articulating when greedy fails and DP is strictly required.

**Depends on:** [`go-fundamentals`](../go-fundamentals/README.md)

## Milestones
- [ ] Milestone 1 — Interval overlap & peak capacity engine: sort-by-start-time + min-heap / two-pointer sweep-line algorithm to calculate peak concurrency; expose `peak-nodes` CLI command.
- [ ] Milestone 2 — Interval merging & free window discovery: merge overlapping time intervals, invert busy schedule to produce available time slots within target ranges; expose `free-slots` CLI command.
- [ ] Milestone 3 — Capacity sizing via binary search on answer space: implement monotonic `canCompleteUnderSLA` feasibility predicate, binary search for optimal capacity with edge case validation; expose `size-capacity` CLI command.
- [ ] Milestone 4 — Greedy dispatchers (EDF/SJF) & formal proof notes: implement scheduling policies, measure schedule lateness, expose `plan` CLI command, and document formal exchange arguments in `docs/greedy-proofs.md`.
- [ ] Milestone 5 — Dynamic Programming extensions (Weighted Intervals & 0/1 Knapsack): implement $O(N \log N)$ Weighted Interval Scheduling using DP + binary search (`sort.Search`), and 0/1 Knapsack task packing for node memory budgets; expose `optimal-weighted` and `pack-node` commands.
