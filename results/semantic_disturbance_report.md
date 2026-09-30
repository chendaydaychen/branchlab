# Semantic validation disturbance experiments

All cases execute the real database read/validate/commit path. A candidate first
reads an observed snapshot; a separate transaction changes the database; the
candidate then attempts strict or semantic commit. Each case is repeated 100
times.

## SEATS-derived

| Disturbance | Expected result | Correct / 100 |
|---|---|---:|
| Another reservation changes capacity/version, seat remains and price is within budget | semantic rebase and commit | 100 |
| Same benign change under strict OCC | reject stale version | 100 |
| Price changes above budget | reject | 100 |
| Last seat is taken | reject | 100 |
| Selected seat is already occupied | reject via database uniqueness | 100 |

False accepts: 0. False rejects: 0. Semantic violations: 0. Business invariant
violations: 0. The audited invariant equates seats sold, reservation rows, and
the sum of customer reservation counters.

## TATP-derived

| Disturbance | Expected result | Correct / 100 |
|---|---|---:|
| Concurrent location update while subscriber and access record remain | semantic rebase and commit | 100 |
| Same location change under strict OCC | reject stale version | 100 |
| Access record removed | reject | 100 |
| Subscriber removed | reject | 100 |

False accepts: 0. False rejects: 0. Semantic violations: 0. Business invariant
violations: 0. The audit checks materialized update records and subscriber
version advancement against actual accepted commits.

These controlled experiments establish correctness only for the declared task
contracts. They do not prove arbitrary LLM-generated semantic contracts safe.
