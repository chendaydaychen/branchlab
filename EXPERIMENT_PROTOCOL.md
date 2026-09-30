# Paper experiment protocol

## Compared controllers

| ID | Shared prefix | Semantic validation | Controller |
|---|---:|---:|---|
| 2PL | no | no | lock shared state through decision |
| OCC | no | no | strict read-version validation |
| Reuse-OCC | yes | no | strict validation of a task-shared snapshot |
| Semantic-OCC | no | yes | semantic rebase without shared-prefix reuse |
| Semantic-Reuse-OCC | yes | yes | complete proposed controller |

All variants must execute the same task, candidates, winner-only materialization
rule, database constraints, and retry budget. Results report task success,
P50/P95/P99 latency, retries, aborts, lock wait, common-prefix executions,
cache hits, semantic rebases, semantic rejections, and invariant violations.
The primary throughput metric is **goodput** (successful commits per elapsed
second). Completion throughput may be reported separately, but retries that
exhaust their budget must not be credited as useful work.

## Required evidence

Run five seeds for each configuration. Sweep workers (1,4,8,16,32),
candidates (1,2,4,8), hotspot sizes (1,4,16,40), and shared-prefix delay
(0,5,20,100,500 ms). Report mean, sample standard deviation, and 95% CI.

The 32-worker confirmation run uses 120 tasks, four candidates per task, and
five seeds for each of 2PL, OCC, and Semantic-Reuse-OCC at h=1 and h=40. The
SEATS-derived generator must assign unique winning seats within every flight;
it rejects configurations exceeding 150 tasks per hot flight.

## Correctness disturbances

For SEATS: depleted capacity, over-budget price, acceptable price/version
change, and duplicate seat/customer attempts. For TATP: concurrent location
updates, missing subscriber, and missing access authorization. The invariant
violation count must remain zero.
