# τ³-bench Airline / DeepSeek Pilot

## Configuration

- Upstream commit: `b7ea9074c1cba482b30687fecdb5c8425fd6f619`
- Domain / split: `airline/base`
- Model: `deepseek/deepseek-flash` for both agent and user simulator
- Temperature: 0.0
- Tasks: 7, 11, 12, 14, 15
- Trials: 1 per task
- Maximum concurrency: 1

## Results

| Task | Reward | DB match | Duration (s) | Agent cost (USD) | User cost (USD) |
|---:|---:|---:|---:|---:|---:|
| 7 | 0 | 0 | 54.08 | 0.01128 | 0.00360 |
| 11 | 1 | 1 | 30.19 | 0.00491 | 0.00294 |
| 12 | 1 | 1 | 30.33 | 0.00553 | 0.00230 |
| 14 | 1 | 1 | 49.69 | 0.01347 | 0.00239 |
| 15 | 1 | 1 | 34.86 | 0.00879 | 0.00230 |
| **Mean / rate** | **0.80** | **0.80** | **39.83** | **0.00880** | **0.00271** |

Additional upstream metrics: read-action match 5/5 (100%), write-action match 6/8 (75%), and all 5 conversations terminated normally.

## Interpretation

The public workload, DeepSeek tool calls, task grader, state database, result persistence, and cost accounting all work end to end. Task 7 failed because the model did not complete two required writes and did not communicate the required aggregate value; there was no API or infrastructure failure.

A separate one-task smoke run of task 7 reached a correct final database state and matched all five expected actions, but failed only the communication check. The different trajectories under the same nominal temperature and seed show that repeated trials are required for any formal claim.

This is a vanilla-agent feasibility baseline, not yet a comparison of 2PL, OCC, and BranchLab.
