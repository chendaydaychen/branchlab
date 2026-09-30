# SEATS five-seed ablation: 40-flight hotspot

Configuration: PostgreSQL 16; 8 workers; 40 tasks × 4 candidates; 40 hot flights; 20 ms common discovery; 10 ms decision; winner-only two-phase materialization; seeds 1–5.

| controller | throughput ops/s, mean ± 95% CI | commits / 160 | retries | common reads |
|---|---:|---:|---:|---:|
| 2pl | 155.99 ± 5.82 | 160.0 | 0.0 | 160.0 |
| occ | 157.32 ± 5.19 | 160.0 | 0.0 | 160.0 |
| reuse_strict | 202.81 ± 12.86 | 160.0 | 0.0 | 40.0 |
| semantic_occ | 153.34 ± 2.62 | 160.0 | 0.0 | 160.0 |
| semantic_reuse | 200.42 ± 16.81 | 160.0 | 0.0 | 40.0 |

Strict variants reject any shared-flight version change. Semantic variants accept a changed version only if flight capacity remains positive and price remains within the task budget, then rebase under the current row lock. Invariant violations: 0 in all recorded runs.
