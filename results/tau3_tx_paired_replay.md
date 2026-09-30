# τ³-bench Paired Transaction Replay

The exact same 78 recorded DeepSeek trajectories are replayed through all three controllers. Immediately before the first write, the harness attempts one benign concurrent change. 2PL blocks the change; OCC and BranchLab receive the identical changed state.

## Results

| Mode | Covered write traces | Accepted | Rejected | Applied / blocked disturbances | Physical reads | Shared-read hits | Semantic rebases |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2pl | 71 | 71 | 0 | 0 / 71 | 642 | 0 | 0 |
| occ | 71 | 0 | 71 | 71 / 0 | 615 | 0 | 0 |
| branchlab | 71 | 71 | 0 | 71 / 0 | 252 | 390 | 130 |

The paired comparison has 71 common disturbance-covered traces. Rejections in this experiment are false rejections because every injected change preserves the pending write's task predicates.

## Interpretation boundary

This is deterministic trace replay over real τ³ tool trajectories. It removes LLM sampling variance and tests transaction acceptance and reuse logic against the actual public workload. It does not measure lock-wait wall time or online multi-branch LLM scheduling; those require the live concurrent runner.
