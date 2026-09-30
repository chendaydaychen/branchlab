# SEATS candidate-count scaling (five seeds)

Configuration: PostgreSQL 16, 8 workers, 40 tasks, 40 hot flights, 20 ms discovery, 10 ms decision, winner-only materialization. Values are mean ± 95% CI.

| candidates | controller | throughput ops/s | P99 ms | common reads | reuse hits | invariant violations |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 2pl | 122.20 ± 9.53 | 95.11 ± 8.78 | 40.0 | 0.0 | 0 |
| 1 | occ | 121.34 ± 4.81 | 98.54 ± 7.03 | 40.0 | 0.0 | 0 |
| 1 | reuse_strict | 100.01 ± 4.96 | 51.17 ± 5.22 | 40.0 | 0.0 | 0 |
| 1 | semantic_occ | 125.86 ± 4.21 | 95.06 ± 5.41 | 40.0 | 0.0 | 0 |
| 1 | semantic_reuse | 106.27 ± 2.88 | 46.49 ± 1.28 | 40.0 | 0.0 | 0 |
| 2 | 2pl | 142.13 ± 5.65 | 92.46 ± 6.55 | 80.0 | 0.0 | 0 |
| 2 | occ | 141.86 ± 3.55 | 92.14 ± 6.84 | 80.0 | 0.0 | 0 |
| 2 | reuse_strict | 153.86 ± 6.98 | 42.58 ± 5.19 | 40.0 | 40.0 | 0 |
| 2 | semantic_occ | 142.02 ± 10.35 | 86.86 ± 8.69 | 80.0 | 0.0 | 0 |
| 2 | semantic_reuse | 152.64 ± 2.62 | 42.81 ± 3.28 | 40.0 | 40.0 | 0 |
| 4 | 2pl | 153.86 ± 5.16 | 83.93 ± 2.53 | 160.0 | 0.0 | 0 |
| 4 | occ | 157.36 ± 3.21 | 84.71 ± 1.55 | 160.0 | 0.0 | 0 |
| 4 | reuse_strict | 202.81 ± 9.34 | 39.14 ± 2.66 | 40.0 | 120.0 | 0 |
| 4 | semantic_occ | 153.50 ± 14.03 | 90.39 ± 13.44 | 160.0 | 0.0 | 0 |
| 4 | semantic_reuse | 200.23 ± 17.24 | 42.22 ± 4.27 | 40.0 | 120.0 | 0 |
| 8 | 2pl | 147.57 ± 6.97 | 94.71 ± 9.90 | 320.0 | 0.0 | 0 |
| 8 | occ | 147.74 ± 6.12 | 88.45 ± 4.56 | 320.0 | 0.0 | 0 |
| 8 | reuse_strict | 222.50 ± 22.54 | 42.49 ± 3.05 | 40.0 | 280.0 | 0 |
| 8 | semantic_occ | 147.65 ± 4.27 | 88.22 ± 10.45 | 320.0 | 0.0 | 0 |
| 8 | semantic_reuse | 213.89 ± 11.77 | 45.99 ± 7.74 | 40.0 | 280.0 | 0 |
