# SEATS five-seed conflict sweep

All configurations use PostgreSQL 16, 8 workers, 40 tasks × 4 candidates, winner-only two-phase materialization, 20 ms shared discovery, and 10 ms decision. Mean ± 95% CI uses Student-t critical value 2.776 for n=5.

| hot flights | controller | throughput ops/s, mean ± 95% CI | commits / 160 | retries | shared reads |
|---:|---|---:|---:|---:|---:|
| 1 | 2pl | 26.91 ± 0.35 | 160.0 | 0.0 | 160.0 |
| 1 | occ | 72.73 ± 3.14 | 149.0 | 180.4 | 160.0 |
| 1 | reuse_strict | 60.15 ± 1.51 | 157.4 | 267.6 | 40.0 |
| 1 | semantic_occ | 157.65 ± 6.03 | 160.0 | 0.0 | 160.0 |
| 1 | semantic_reuse | 169.29 ± 4.60 | 160.0 | 0.0 | 40.0 |
| 16 | 2pl | 153.55 ± 5.87 | 160.0 | 0.0 | 160.0 |
| 16 | occ | 157.33 ± 5.27 | 160.0 | 0.0 | 160.0 |
| 16 | reuse_strict | 178.91 ± 8.41 | 160.0 | 24.0 | 40.0 |
| 16 | semantic_occ | 154.55 ± 3.56 | 160.0 | 0.0 | 160.0 |
| 16 | semantic_reuse | 204.49 ± 16.69 | 160.0 | 0.0 | 40.0 |
| 40 | 2pl | 155.99 ± 5.82 | 160.0 | 0.0 | 160.0 |
| 40 | occ | 157.32 ± 5.19 | 160.0 | 0.0 | 160.0 |
| 40 | reuse_strict | 202.81 ± 12.86 | 160.0 | 0.0 | 40.0 |
| 40 | semantic_occ | 153.34 ± 2.62 | 160.0 | 0.0 | 160.0 |
| 40 | semantic_reuse | 200.42 ± 16.81 | 160.0 | 0.0 | 40.0 |
