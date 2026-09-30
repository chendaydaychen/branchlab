# τ³-bench Airline / DeepSeek Mutation Baseline

## Configuration

- Upstream commit: `b7ea9074c1cba482b30687fecdb5c8425fd6f619`
- Domain / split: `airline/base`
- Model: `deepseek/deepseek-flash` for agent and user simulator
- Tasks: 26 mutation-bearing tasks selected deterministically from 50 base tasks
- Trials: 3 per task; 78 simulations total
- Temperature: 0.0; maximum concurrency: 3

## Overall results

| Metric | Result |
|---|---:|
| End-to-end reward / Pass^1 | 57/78 (73.1%) |
| Final database state match | 58/78 (74.4%) |
| Read-action match | 153/159 (96.2%) |
| Write-action match | 120/147 (81.6%) |
| Communication assertions met | 24/27 (88.9%) |
| Mean latency | 41.08 s |
| Latency p50 / p95 / p99 | 37.86 / 73.46 / 94.37 s |
| Agent-model cost | $0.7659 total |
| User-simulator cost | $0.2071 total |
| Combined cost | $0.9729 total; $0.0125/simulation |
| LLM calls | 1118 |
| Provider prompt-cache hit / miss | 5,102,464 / 794,917 tokens (86.5% hit) |
| Normal termination | 78/78 (100%) |

The upstream console additionally reports Pass^2 = 0.654 and Pass^3 = 0.615. These decreasing reliability values show that repeated correctness is materially harder than a single successful run.

Provider-side prompt caching is reported separately from BranchLab reuse. It mainly captures repeated request prefixes recognized by DeepSeek; BranchLab's contribution must be measured as additional sharing of branch state and tool results under semantic validity.

| Role | LLM calls | Prompt tokens | Completion tokens | Cache hit | Cache miss |
|---|---:|---:|---:|---:|---:|
| assistant | 694 | 5,468,782 | 447,120 | 4,800,384 | 668,398 |
| user | 424 | 428,599 | 139,420 | 302,080 | 126,519 |

## Per-task stability

| Task | E2E pass | DB match | Mean latency (s) | Mean total cost (USD) | Write actions |
|---:|---:|---:|---:|---:|---:|
| 7 | 0/3 | 1/3 | 77.40 | 0.0217 | 5/9 |
| 8 | 3/3 | 3/3 | 23.84 | 0.0069 | 3/3 |
| 11 | 3/3 | 3/3 | 28.08 | 0.0079 | 3/3 |
| 12 | 3/3 | 3/3 | 28.97 | 0.0077 | 3/3 |
| 14 | 3/3 | 3/3 | 45.33 | 0.0151 | 6/6 |
| 15 | 1/3 | 1/3 | 34.44 | 0.0116 | 1/3 |
| 16 | 3/3 | 3/3 | 25.83 | 0.0089 | 3/3 |
| 17 | 3/3 | 3/3 | 37.75 | 0.0125 | 9/9 |
| 18 | 1/3 | 1/3 | 62.51 | 0.0222 | 15/15 |
| 19 | 3/3 | 3/3 | 18.83 | 0.0047 | 3/3 |
| 20 | 3/3 | 3/3 | 35.72 | 0.0125 | 3/3 |
| 21 | 3/3 | 3/3 | 58.87 | 0.0181 | 6/6 |
| 22 | 3/3 | 3/3 | 25.83 | 0.0093 | 9/9 |
| 23 | 3/3 | 3/3 | 79.40 | 0.0253 | 12/12 |
| 24 | 3/3 | 3/3 | 38.76 | 0.0126 | 3/3 |
| 25 | 3/3 | 3/3 | 28.41 | 0.0080 | 3/3 |
| 29 | 0/3 | 0/3 | 39.38 | 0.0107 | 0/6 |
| 30 | 3/3 | 3/3 | 22.84 | 0.0059 | 3/3 |
| 32 | 0/3 | 0/3 | 48.00 | 0.0133 | 0/6 |
| 33 | 2/3 | 2/3 | 40.16 | 0.0110 | 5/6 |
| 35 | 3/3 | 3/3 | 55.32 | 0.0148 | 3/3 |
| 37 | 2/3 | 2/3 | 40.93 | 0.0120 | 2/3 |
| 39 | 0/3 | 0/3 | 44.23 | 0.0131 | 6/9 |
| 40 | 3/3 | 3/3 | 13.01 | 0.0026 | 3/3 |
| 42 | 2/3 | 2/3 | 43.86 | 0.0128 | 6/6 |
| 44 | 1/3 | 1/3 | 70.45 | 0.0229 | 5/9 |

## Evidence boundary

This run is the vanilla DeepSeek baseline on an authoritative public agent benchmark. It establishes task difficulty, variance, cost, latency, action traces, and final-state grading. It does not yet measure 2PL, OCC, or BranchLab, because all three must be evaluated through the same transaction-aware execution adapter before a causal comparison is valid.

The gap between read-action match (high) and write-action / DB match (lower) supports focusing the system contribution on safe speculative execution and commit semantics rather than on information retrieval alone.
