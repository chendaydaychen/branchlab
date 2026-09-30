# TATP-derived single-hotspot result

This is a BranchLab TATP-derived experiment, **not** an official BenchBase/TATP result.
TATP entity/transaction semantics follow the public BenchBase implementation; row versions and
the branch audit table are experimental extensions. All runs: PostgreSQL 16, 8 workers,
30 tasks × 4 candidate branches, one hot subscriber, 20 ms discovery, 10 ms decision,
12 OCC retries, seeds 1–3.

| mode | throughput ops/s (mean ± sd) | commits / 120 | failures / 120 | aborts | common reads | lock wait |
|---|---:|---:|---:|---:|---:|---:|
| 2pl | 27.04 ± 0.08 | 120.0 | 0.0 | 0.0 | 120.0 | 28985 ms |
| occ | 29.34 ± 0.24 | 83.3 | 36.7 | 556.3 | 120.0 | 0 ms |
| reuse | 21.21 ± 0.41 | 109.3 | 10.7 | 830.7 | 30.0 | 0 ms |

## Interpretation

- 2PL is the only mode with all 120 commits, but it holds the subscriber row lock across
  discovery and decision, producing roughly 29 s aggregate wait per run.
- OCC has slightly higher attempted-operation throughput, but the single writer hotspot creates
  hundreds of validation retries and about 37 exhausted branches.
- Reuse performs exactly one common read per task (30 rather than 120), with 90 sibling cache
  hits. It does **not** win throughput on this deliberately adversarial write hotspot: the shared
  snapshot is often stale before a sibling can commit, so validation correctly causes retries.
- Thus these runs support the safety and compute-elimination claims, but do not yet support an
  unconditional end-to-end speedup claim. A mixed read/private-write TATP scenario and SEATS
  should be added before making a broader performance claim.

Raw JSON files are stored in the results directory with tatp prefixes.
