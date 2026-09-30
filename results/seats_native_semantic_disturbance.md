# PostgreSQL isolation under semantic disturbances

Repetitions per controller/case: 100.

| controller | disturbance | accepted | rejected | false accepts | false rejects |
|---|---|---:|---:|---:|---:|
| branchlab | benign_price_change | 100 | 0 | 0 | 0 |
| branchlab | over_budget_change | 0 | 100 | 0 | 0 |
| pg_rc | benign_price_change | 100 | 0 | 0 | 0 |
| pg_rc | over_budget_change | 100 | 0 | 100 | 0 |
| pg_rr | benign_price_change | 0 | 100 | 0 | 100 |
| pg_rr | over_budget_change | 0 | 100 | 0 | 0 |
| pg_ssi | benign_price_change | 0 | 100 | 0 | 100 |
| pg_ssi | over_budget_change | 0 | 100 | 0 | 0 |
