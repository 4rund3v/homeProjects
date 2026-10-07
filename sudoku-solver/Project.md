# Sudoku Solver

## What this project exists to solve
Reinforce algorithmic thinking, testing discipline, and Python design by implementing a Sudoku solver. The focus is not speed — it is correctness, testability, and the ability to explain every design choice.

## Success criteria / completion metrics
- A working solver that solves standard 9×9 puzzles and rejects invalid inputs.
- Correctness proven by tests, not by eyeballing outputs.
- At least one benchmark comparing naive backtracking vs. constraint propagation.
- A property-based test confirming that any produced board is a valid solution.
- `uv run pytest`, `uv run ruff`, and `uv run mypy --strict` all pass.

## Prerequisites and dependencies
- `python-refresh` testing and typing conventions.

## Tools, libraries, and runtime
- `uv` for environment and dependencies.
- Runtime: standard library only. No solver libraries.
- Dev: `pytest`, `pytest-cov`, `ruff`, `mypy --strict`, `hypothesis`, `cProfile`/`pyinstrument` (profiling).

## Learning objectives (skills practiced)
- Backtracking with forward checking and constraint propagation.
- Invariant-driven testing: every assumption is a test.
- Property-based testing with Hypothesis.
- Algorithmic complexity and when "fast enough" is acceptable.
- Benchmarking with pytest-benchmark or `timeit`.
- Profiling to confirm where time is spent (and where it is not).

## Architecture / design note
A clean separation between representation, solver, and CLI:

```
src/
  board.py       # Board representation, parsing, validation, display
  solver.py      # Backtracking solver + constraint propagation
  cli.py         # argparse entrypoint
tests/
  test_board.py
  test_solver.py
  test_properties.py
```

Key design decisions to make explicit:
- Internal representation: flat list vs. 2D array vs. bitmask. Each has implications for speed and readability.
- Forward checking: prune candidates before recursing.
- Heuristic: minimum remaining values (MRV) or static row/col ordering? Measure both.
- Constraint propagation: maintain candidate sets incrementally vs. recompute.

## Test strategy
- Unit tests for `Board` parsing and validation using known puzzles and invalid boards.
- Solver tests with fixtures from known puzzle databases (include a few hard puzzles).
- Property-based test: `assert solver.solve(board).is_valid()`.
- Regression tests for edge cases: empty board, already-solved board, board with no solution.
- Benchmark comparing heuristic choices; record in `NOTES.md` with profiler evidence.

## Documentation checklist
- `README.md` with setup, usage, algorithm overview, and complexity discussion.
- `NOTES.md` with profiling results, heuristic comparison, and tradeoffs.
- Docstrings with type annotations; `mypy --strict` must pass.

## API contract
No HTTP API. CLI entry point accepts puzzle strings or files; returns solution or error code.

## UI / status surfaces
CLI only. ASCII board rendering for human inspection is sufficient.

## Security boundaries to think about
- Puzzle input should be validated before solving (length, characters).
- Extremely pathological puzzles could cause exponential time — document the timeout strategy or input bounds.
- If accepting puzzles from untrusted sources, treat input as data, not code.

## Profiling plan
- Profile the solver on a hard puzzle with `cProfile` and `pyinstrument`.
- Confirm that time is spent in constraint checking, not in Python overhead.
- Benchmark naive backtracking vs. constraint propagation + MRV; report wall time and iteration count.

## How this project fits into the curriculum
This is the first project after language fundamentals. It reinforces test discipline from `python-refresh` and introduces profiling habits. The algorithmic thinking is generalizable and unrelated to Go — that's intentional: Python and Go are practiced in parallel so each language's idioms stay distinct.

## Suggested milestone walkthrough
1. **Board representation.** Define `Board` with parsing, validation, and display. Write exhaustive tests for valid/invalid inputs.
2. **Naive backtracking.** Implement without optimization. Verify correctness on easy puzzles. Measure baseline time.
3. **Optimization.** Add forward checking and/or MRV. Benchmark against baseline. Document the speedup and the complexity change.
4. **Property tests.** Add Hypothesis tests for solution validity and symmetry. Inspect any counterexamples.

## Reference notes and resources
- Knuth, "Dancing Links" (optional deep dive if curious about exact cover).
- CSP (constraint satisfaction problems) background for understanding why propagation helps.
- Python `timeit` and `cProfile` documentation.
