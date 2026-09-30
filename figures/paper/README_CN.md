# BranchLab 论文图使用说明

所有图均生成三种格式：PDF（论文优先）、SVG（编辑优先）和 300 dpi PNG（预览）。
源文件为 `generate_paper_figures.py`，运行方式：

```bash
cd /mnt/z/at/branchlab
python3 figures/paper/generate_paper_figures.py
```

## Figure 1：系统架构

文件：`fig1-branchlab-architecture.*`

建议放在 System Overview 开头，跨双栏。

建议英文 caption：

> **BranchLab architecture.** The runtime jointly manages data state ($D$),
> branch state ($B$), and task semantics ($S$). It executes a shared read-only
> prefix once, forks isolated LLM continuations at the first write intent, and
> materializes only the winning branch after deterministic semantic validation.

## Figure 2：事务生命周期

文件：`fig2-transaction-lifecycle.*`

建议放在 Transaction Model 或 Execution Protocol 小节，跨双栏。

建议英文 caption：

> **Lifecycle of a multi-branch Agent transaction.** A single shared prefix
> produces a frozen base snapshot. Candidate continuations inherit immutable
> observations but keep post-fork state private. Only the selected branch is
> validated and materialized; siblings are discarded without visible effects.

## Figure 3：语义契约流水线

文件：`fig3-semantic-contract-pipeline.*`

建议放在 Semantic Contract 小节，跨双栏。这张图用于回答“LLM 是否直接决定提交”以及
“安全模板是否针对具体 benchmark 任务”两个问题。

建议英文 caption：

> **Trusted semantic-contract pipeline.** The LLM proposes task-specific clauses,
> while an operation-level safety floor supplies non-removable predicates. The
> hardened contract is bound to the branch, snapshot, operation, and canonical
> arguments. A deterministic validator—not the LLM—decides whether to rebase and
> commit or reject and replan.

## Figure 4：2PL、OCC 与 BranchLab 对比

文件：`fig4-controller-comparison.*`

建议放在 Motivation 或 Background 末尾，跨双栏，也适合组会解释核心矛盾。

建议英文 caption：

> **Physical conflicts versus task conflicts.** 2PL prevents concurrent changes
> by holding locks across Agent reasoning; strict OCC aborts on any observed
> version change. BranchLab validates task predicates, accepting benign changes
> while rejecting changes that invalidate authorization or task correctness.

## Figure 5：核心实验证据摘要

文件：`fig5-evidence-summary.*`

建议作为 Evaluation Overview，跨双栏。Panel (b) 把“良性变化实际进入且事务仍提交”
记作 admitted；把“有害变化被阻止或拒绝”记作 prevented。因此 2PL 的良性 admitted
为 0，而 harmful prevented 为 71（通过阻塞实现）。

建议英文 caption：

> **Summary of key evidence.** (a) Real tau-bench/DeepSeek traces contain substantial
> exact sharing opportunities. (b) BranchLab admits all 71 benign changes while
> preventing every harmful change; 2PL prevents both by blocking, whereas strict
> OCC rejects both after version validation. (c) Under the 32-worker single-hotspot
> long-stress configuration, BranchLab improves successful goodput while preserving
> 100% completion in the recorded runs. Error bars show 95% confidence intervals
> over five seeds.

## 视觉规范

- 双栏宽度约 7.05 英寸，适配 VLDB/ACM 双栏版面。
- 不依赖渐变、阴影或三维效果；色彩只承担稳定类别编码。
- 关键语义同时通过文字、位置或纹理表达，灰度打印仍可理解。
- PDF 使用 TrueType 字体嵌入；SVG 保留文本，便于 Inkscape/Illustrator 修改。
- 最终排版时优先使用 PDF，不要把 PNG 当作论文主图。
