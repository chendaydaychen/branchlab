# BranchLab：参考风格论文图

本目录按照所给参考图的视觉语言重新设计：浅色大框架、虚线子系统边界、模块化组件、
清晰的数据流与控制流。所有图均输出 PDF、SVG 和 320 dpi PNG。

## 图表清单

1. `fig-r1-overall-architecture.*`：BranchLab 总体架构。建议作为论文主系统图。
2. `fig-r2-shared-prefix-branching.*`：公共前缀执行、分支隔离和 winner-only materialization。
3. `fig-r3-semantic-contract-engine.*`：分层语义契约与可信提交协议。
4. `fig-r4-passenger-update-example.*`：乘客姓名修改的端到端实例，适合 Motivation 或 Overview。

## 推荐 caption

### Figure R1

> **Overall architecture of BranchLab.** The speculative transaction manager
> executes a shared prefix and isolates post-fork continuations. The unified state
> tracker jointly records data, branch, and task-semantic state. The semantic
> concurrency-control engine hardens and binds LLM-proposed task clauses before a
> deterministic validator authorizes winner-only materialization.

### Figure R2

> **Shared-prefix execution and isolated branching.** Candidate continuations
> inherit the same immutable observations but keep post-fork messages and writes in
> private namespaces. The resolver selects one winner for validation and discards
> sibling branches without visible effects.

### Figure R3

> **Semantic contract engine.** The LLM extracts task-specific clauses, while the
> operation policy supplies a reusable, non-removable safety floor. The trusted
> runtime binds the hardened contract to a branch, snapshot, operation, and exact
> arguments, then validates it against the latest database state.

### Figure R4

> **Passenger-update example.** A phone-number update is outside the semantic
> dependency set and can be safely rebased, whereas cancellation violates a hard
> predicate and forces rejection. Thus BranchLab distinguishes task conflicts from
> arbitrary physical version changes.

## 生成命令

```bash
cd /mnt/z/at/branchlab
python3 figures/paper_refstyle/generate_reference_style_figures.py
```

论文排版优先使用 PDF，后续编辑使用 SVG，PNG 仅用于预览。
