# TATP-derived five-seed ablation: single-subscriber hotspot

Configuration: PostgreSQL 16; 8 workers; 20 tasks × 4 candidates; one hot subscriber; 20 ms discovery; 10 ms decision; seeds 1–5. This is a TATP-derived experiment, not an official BenchBase score.

| controller | throughput ops/s, mean ± 95% CI | commits / 80 | retries | common reads |
|---|---:|---:|---:|---:|
| 2pl | 26.76 ± 0.86 | 80.0 | 0.0 | 80.0 |
| occ | 77.93 ± 5.30 | 74.4 | 85.0 | 80.0 |
| reuse_strict | 62.05 ± 0.89 | 79.4 | 121.0 | 20.0 |
| semantic_occ | 152.66 ± 2.80 | 80.0 | 0.0 | 80.0 |
| semantic_reuse | 167.95 ± 5.85 | 80.0 | 0.0 | 20.0 |
