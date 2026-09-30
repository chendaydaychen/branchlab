# TPC-C-derived contention point

workers=16, candidates=4, hot_items=1, seeds=5

| mode | throughput mean +/- sd | mean aborts | total failures | mean discovery executions |
|---|---:|---:|---:|---:|
| 2pl | 41.98 +/- 1.83 | 0.0 | 0 | 160.0 |
| occ | 61.04 +/- 3.98 | 395.4 | 25 | 160.0 |
| reuse | 65.12 +/- 2.59 | 388.8 | 23 | 40.0 |
