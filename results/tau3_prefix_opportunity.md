# τ³-bench Multi-branch Prefix Opportunity

Each task's three independent DeepSeek trials is treated as three candidate execution branches. Calls are identical only when both the tool name and canonicalized arguments match.

## Aggregate

| Metric | Result |
|---|---:|
| Tasks / traces | 26 / 78 |
| Actual tool calls | 772 |
| Nodes after exact prefix-trie sharing | 435 |
| Calls removable by prefix sharing | 337 (43.7%) |
| Tasks with a common three-branch prefix | 23/26 (88.5%) |
| Mean common prefix length | 5.23 calls |
| Read calls | 642 |
| Repeated exact reads within a task | 391 (60.9%) |

Prefix-trie savings are conservative: calls after branches diverge are not merged even if they later become identical. Exact-read memoization is an upper bound because a cached result is reusable only while its semantic dependencies remain valid.

## Per task

| Task | Trace lengths | Common prefix | Prefix-shareable | Repeated reads |
|---:|---:|---:|---:|---:|
| 7 | 13/9/12 | 0 | 2 | 14 |
| 8 | 8/8/8 | 1 | 9 | 14 |
| 11 | 7/7/7 | 7 | 14 | 12 |
| 12 | 5/5/5 | 5 | 10 | 8 |
| 14 | 8/8/8 | 8 | 16 | 12 |
| 15 | 6/5/7 | 5 | 10 | 10 |
| 16 | 6/6/6 | 6 | 12 | 10 |
| 17 | 9/9/9 | 7 | 16 | 12 |
| 18 | 26/25/24 | 20 | 42 | 38 |
| 19 | 5/5/5 | 5 | 10 | 8 |
| 20 | 9/6/6 | 1 | 7 | 10 |
| 21 | 12/14/12 | 10 | 22 | 20 |
| 22 | 9/9/9 | 6 | 15 | 12 |
| 23 | 12/10/10 | 0 | 3 | 12 |
| 24 | 20/18/22 | 0 | 4 | 36 |
| 25 | 6/7/4 | 2 | 4 | 6 |
| 29 | 6/3/4 | 2 | 6 | 6 |
| 30 | 4/4/4 | 4 | 8 | 6 |
| 32 | 8/8/8 | 5 | 12 | 14 |
| 33 | 6/6/6 | 1 | 7 | 8 |
| 35 | 10/8/10 | 5 | 15 | 16 |
| 37 | 12/12/12 | 4 | 10 | 20 |
| 39 | 28/11/11 | 8 | 18 | 16 |
| 40 | 3/3/2 | 1 | 4 | 3 |
| 42 | 10/11/10 | 8 | 18 | 16 |
| 44 | 29/30/27 | 15 | 43 | 52 |

## Interpretation

This analysis establishes that shared work exists in real public Agent trajectories. It does not claim the full theoretical savings are realized: the runtime experiment must measure cache lookup overhead, invalidation, semantic validation, and LLM-prefix reuse separately.
