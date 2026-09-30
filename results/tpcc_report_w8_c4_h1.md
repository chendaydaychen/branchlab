# TPC-C-derived contention point

workers=8, candidates=4, hot_items=1, seeds=5

| mode | throughput mean +/- sd | mean aborts | total failures | mean discovery executions |
|---|---:|---:|---:|---:|
| 2pl | 39.87 +/- 1.65 | 0.0 | 0 | 160.0 |
| occ | 50.20 +/- 3.74 | 206.0 | 15 | 160.0 |
| reuse | 56.87 +/- 4.03 | 203.2 | 5 | 40.0 |
