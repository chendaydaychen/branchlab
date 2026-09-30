# SEATS five-seed ablation: single-flight hotspot

Configuration: PostgreSQL 16; 8 workers; 40 tasks × 4 candidates; one hot flight; 20 ms common discovery; 10 ms decision; winner-only two-phase materialization; seeds 1–5.

| controller | throughput ops/s, mean ± 95% CI | commits / 160 | retries | common reads |
|---|---:|---:|---:|---:|
| 2pl | 26.91 ± 0.35 | 160.0 | 0.0 | 160.0 |
| occ | 72.73 ± 3.14 | 149.0 | 180.4 | 160.0 |
| reuse_strict | 60.15 ± 1.51 | 157.4 | 267.6 | 40.0 |
| semantic_occ | 157.65 ± 6.03 | 160.0 | 0.0 | 160.0 |
| semantic_reuse | 169.29 ± 4.60 | 160.0 | 0.0 | 40.0 |

Strict variants reject any shared-flight version change. Semantic variants accept a changed version only if flight capacity remains positive and price remains within the task budget, then rebase under the current row lock. Invariant violations: 0 in all recorded runs.
