# SEATS 32-worker long-run confirmation (five seeds)

Configuration: PostgreSQL 16, 32 workers, 120 tasks, 4 candidates/task (480 branch operations/run), 20 ms discovery, 10 ms decision, winner-only materialization. Values are mean ± 95% CI.

| h | controller | goodput ops/s | success % | P99 ms | retries | prefix executions | invariant violations |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | 2pl | 27.01 ± 0.19 | 100.00 ± 0.00 | 1243.87 ± 17.79 | 0.0 ± 0.0 | 480.0 | 0 |
| 1 | occ | 78.38 ± 3.52 | 84.96 ± 0.22 | 1157.10 ± 11.29 | 1143.6 ± 53.0 | 480.0 | 0 |
| 1 | semantic_reuse | 179.70 ± 5.13 | 100.00 ± 0.00 | 440.87 ± 56.93 | 0.0 ± 0.0 | 120.0 | 0 |
| 40 | 2pl | 258.79 ± 26.96 | 100.00 ± 0.00 | 194.70 ± 22.27 | 0.0 ± 0.0 | 480.0 | 0 |
| 40 | occ | 245.36 ± 35.28 | 100.00 ± 0.00 | 198.31 ± 19.64 | 0.0 ± 0.0 | 480.0 | 0 |
| 40 | semantic_reuse | 220.95 ± 23.52 | 100.00 ± 0.00 | 183.71 ± 28.40 | 0.0 ± 0.0 | 120.0 | 0 |

## Main effects

- h=1: complete design is 2.29× OCC and 6.65× 2PL in successful goodput (179.70 vs 78.38 vs 27.01 ops/s).
- h=40: complete design is 0.90× OCC and 0.85× 2PL in successful goodput (220.95 vs 245.36 vs 258.79 ops/s).
