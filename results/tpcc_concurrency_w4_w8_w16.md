# TPC-C-derived high-contention concurrency sweep

candidates=4, hot_items=1, tasks=40, discovery_ms=20, think_ms=30, seeds=5

| workers | mode | throughput mean +/- sd | mean aborts | total failures |
|---:|---|---:|---:|---:|
| 4 | 2pl | 34.52 +/- 1.67 | 0.0 | 0 |
| 4 | occ | 37.97 +/- 1.90 | 78.2 | 0 |
| 4 | reuse | 46.08 +/- 3.16 | 82.2 | 0 |
| 8 | 2pl | 39.87 +/- 1.65 | 0.0 | 0 |
| 8 | occ | 50.20 +/- 3.74 | 206.0 | 15 |
| 8 | reuse | 56.87 +/- 4.03 | 203.2 | 5 |
| 16 | 2pl | 41.98 +/- 1.83 | 0.0 | 0 |
| 16 | occ | 61.04 +/- 3.98 | 395.4 | 25 |
| 16 | reuse | 65.12 +/- 2.59 | 388.8 | 23 |
