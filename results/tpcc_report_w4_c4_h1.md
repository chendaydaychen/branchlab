# TPC-C-derived contention point

workers=4, candidates=4, hot_items=1, seeds=5

| mode | throughput mean +/- sd | mean aborts | total failures | mean discovery executions |
|---|---:|---:|---:|---:|
| 2pl | 34.52 +/- 1.67 | 0.0 | 0 | 160.0 |
| occ | 37.97 +/- 1.90 | 78.2 | 0 | 160.0 |
| reuse | 46.08 +/- 3.16 | 82.2 | 0 | 40.0 |
