# SEATS shared-prefix cost scaling (five seeds)

Configuration: PostgreSQL 16, 8 workers, 40 tasks, 4 candidates/task, 40 hot flights, 10 ms decision, winner-only materialization. The 20 ms point reuses the identical c=4 candidate-scaling runs. Values are mean ± 95% CI.

The primary metric is end-to-end throughput. Per-operation latency is not used here because reused prefix work is accounted at task level rather than inside each branch transaction's latency timer.

| prefix cost ms | controller | throughput ops/s | prefix executions | reuse hits | invariant violations |
|---:|---|---:|---:|---:|---:|
| 0 | 2pl | 212.83 ± 15.17 | 160.0 | 0.0 | 0 |
| 0 | occ | 214.45 ± 14.64 | 160.0 | 0.0 | 0 |
| 0 | reuse_strict | 208.50 ± 11.22 | 40.0 | 120.0 | 0 |
| 0 | semantic_occ | 211.82 ± 8.78 | 160.0 | 0.0 | 0 |
| 0 | semantic_reuse | 201.49 ± 11.92 | 40.0 | 120.0 | 0 |
| 5 | 2pl | 190.37 ± 6.97 | 160.0 | 0.0 | 0 |
| 5 | occ | 184.89 ± 11.49 | 160.0 | 0.0 | 0 |
| 5 | reuse_strict | 188.28 ± 10.02 | 40.0 | 120.0 | 0 |
| 5 | semantic_occ | 188.80 ± 4.64 | 160.0 | 0.0 | 0 |
| 5 | semantic_reuse | 184.49 ± 14.44 | 40.0 | 120.0 | 0 |
| 20 | 2pl | 153.86 ± 5.16 | 160.0 | 0.0 | 0 |
| 20 | occ | 157.36 ± 3.21 | 160.0 | 0.0 | 0 |
| 20 | reuse_strict | 202.81 ± 9.34 | 40.0 | 120.0 | 0 |
| 20 | semantic_occ | 153.50 ± 14.03 | 160.0 | 0.0 | 0 |
| 20 | semantic_reuse | 200.23 ± 17.24 | 40.0 | 120.0 | 0 |
| 100 | 2pl | 58.04 ± 1.55 | 160.0 | 0.0 | 0 |
| 100 | occ | 57.98 ± 0.87 | 160.0 | 0.0 | 0 |
| 100 | reuse_strict | 121.44 ± 6.19 | 40.0 | 120.0 | 0 |
| 100 | semantic_occ | 57.28 ± 1.56 | 160.0 | 0.0 | 0 |
| 100 | semantic_reuse | 122.95 ± 6.00 | 40.0 | 120.0 | 0 |
| 500 | 2pl | 14.81 ± 0.06 | 160.0 | 0.0 | 0 |
| 500 | occ | 14.76 ± 0.13 | 160.0 | 0.0 | 0 |
| 500 | reuse_strict | 48.28 ± 0.32 | 40.0 | 120.0 | 0 |
| 500 | semantic_occ | 14.80 ± 0.10 | 160.0 | 0.0 | 0 |
| 500 | semantic_reuse | 48.87 ± 0.70 | 40.0 | 120.0 | 0 |

## Mechanism effect

- 0 ms: Semantic-Reuse-OCC is 0.95× the throughput of Semantic-OCC (201.49 vs 211.82 ops/s).
- 5 ms: Semantic-Reuse-OCC is 0.98× the throughput of Semantic-OCC (184.49 vs 188.80 ops/s).
- 20 ms: Semantic-Reuse-OCC is 1.30× the throughput of Semantic-OCC (200.23 vs 153.50 ops/s).
- 100 ms: Semantic-Reuse-OCC is 2.15× the throughput of Semantic-OCC (122.95 vs 57.28 ops/s).
- 500 ms: Semantic-Reuse-OCC is 3.30× the throughput of Semantic-OCC (48.87 vs 14.80 ops/s).
