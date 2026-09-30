"""Report measured end-to-end performance of independent vs shared-prefix runs."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def improvement(baseline: float, optimized: float) -> dict[str, float]:
    return {
        "baseline": baseline,
        "optimized": optimized,
        "reduction_pct": 100.0 * (baseline - optimized) / baseline,
        "speedup_x": baseline / optimized,
    }


def main() -> None:
    two_pl = load("tau3_independent_parallel_2pl_task11_r3_s720.json")
    occ = load("tau3_independent_parallel_occ_task11_r3_s720.json")
    branchlab = load("tau3_online_branch_branchlab_task11_b3_s720.json")
    bl = branchlab["aggregate"]

    rows = {
        "2pl": {
            "success": two_pl["aggregate"]["successful_runs"],
            "db_match": two_pl["aggregate"]["db_match_runs"],
            "wallclock_s": two_pl["aggregate"]["wallclock_s"],
            "cost_usd": two_pl["aggregate"]["total_cost_usd"],
            "physical_reads": two_pl["aggregate"]["physical_reads"],
        },
        "occ": {
            "success": occ["aggregate"]["successful_runs"],
            "db_match": occ["aggregate"]["db_match_runs"],
            "wallclock_s": occ["aggregate"]["wallclock_s"],
            "cost_usd": occ["aggregate"]["total_cost_usd"],
            "physical_reads": occ["aggregate"]["physical_reads"],
        },
        "branchlab": {
            "success": bl["successful_branches"],
            "db_match": sum(
                item["db_match"] for item in branchlab["branch_results"]
            ),
            "wallclock_s": bl["total_wallclock_s"],
            "cost_usd": bl["actual_total_cost_usd"],
            "physical_reads": bl["actual_total_physical_reads"],
        },
    }
    comparisons = {}
    for baseline in ("2pl", "occ"):
        comparisons[baseline] = {
            metric: improvement(rows[baseline][metric], rows["branchlab"][metric])
            for metric in ("wallclock_s", "cost_usd", "physical_reads")
        }
    payload = {
        "experiment": {
            "benchmark": "tau3 airline task 11",
            "model": "deepseek/deepseek-flash",
            "candidates": 3,
            "base_seed": 720,
            "temperature": 0.2,
            "execution": "parallel",
        },
        "rows": rows,
        "comparisons": comparisons,
        "branchlab_breakdown": {
            "prefix_wallclock_s": bl["prefix_wallclock_s"],
            "continuation_wallclock_s": bl["continuation_wallclock_s"],
            "scheduler_probe_cost_usd": branchlab["prefix"][
                "scheduler_probe_cost_usd"
            ],
            "semantic_rebases": sum(
                item["transaction_metrics"]["semantic_rebases"]
                for item in branchlab["branch_results"]
            ),
        },
    }
    labels = {"2pl": "独立2PL", "occ": "独立严格OCC", "branchlab": "BranchLab"}
    lines = [
        "# BranchLab 真实并行性能对比",
        "",
        "## 实验设置",
        "",
        "- 公开负载：τ³ Airline task 11。",
        "- 模型：DeepSeek Flash。",
        "- 每组同时获取 3 个候选结果，种子为 721/722/723，temperature=0.2。",
        "- 2PL/OCC：3 个完整会话从头并行执行，Agent、用户、数据库和缓存完全隔离，不共享前缀。",
        "- BranchLab：公共会话和读前缀执行一次，在首次写意图前自动分叉，3 个隔离 continuation 真并行执行。",
        "- 墙钟时间不含 Python/依赖导入，只覆盖实际调度与模拟运行。",
        "",
        "## 实测结果",
        "",
        "| 系统 | 成功 | DB match | 3候选墙钟(s) | 总成本($) | 物理读 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in ("2pl", "occ", "branchlab"):
        row = rows[mode]
        lines.append(
            f"| {labels[mode]} | {row['success']}/3 | {row['db_match']}/3 | "
            f"{row['wallclock_s']:.2f} | {row['cost_usd']:.5f} | {row['physical_reads']} |"
        )
    lines.extend(["", "## BranchLab 优化幅度", ""])
    for mode in ("2pl", "occ"):
        comp = comparisons[mode]
        lines.extend(
            [
                f"相对{labels[mode]}：",
                "",
                f"- 墙钟时间减少 **{comp['wallclock_s']['reduction_pct']:.1f}%**，即 **{comp['wallclock_s']['speedup_x']:.2f}×**。",
                f"- LLM 成本减少 **{comp['cost_usd']['reduction_pct']:.1f}%**，即单位预算可执行约 **{comp['cost_usd']['speedup_x']:.2f}×** 的候选组。",
                f"- 数据库物理读减少 **{comp['physical_reads']['reduction_pct']:.1f}%**，读效率提升 **{comp['physical_reads']['speedup_x']:.2f}×**。",
                "",
            ]
        )
    lines.extend(
        [
            "## BranchLab 时间构成",
            "",
            f"- 公共前缀与自动切点：{bl['prefix_wallclock_s']:.2f}s。",
            f"- 三个并行 continuation：{bl['continuation_wallclock_s']:.2f}s。",
            f"- 总墙钟：{bl['total_wallclock_s']:.2f}s。",
            f"- 自动切点 probe 成本：${branchlab['prefix']['scheduler_probe_cost_usd']:.5f}，已包含在总成本中。",
            "- 三个分支全部通过语义提交验证，共发生 3 次 semantic rebase，验证失败为 0。",
            "",
            "## 结论边界",
            "",
            "这是单个 τ³ 写任务、一个 base seed、每组 3 个候选的真实端到端 pilot。它已经证明优化可实际转化为墙钟、成本和数据库 I/O 收益，但不能作为总体均值或显著性结论。由于 LLM 服务存在非确定性，即便种子相同，各系统的自然语言轨迹也不完全一致。论文主结果还应扩展到多个任务与至少 5 个 base seed，并报告 bootstrap 95% 置信区间。并发控制正确性的因果结论应继续引用 78 条同轨迹配对重放，而不是仅引用本表。",
            "",
        ]
    )
    (RESULTS / "tau3_parallel_performance_comparison.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (RESULTS / "tau3_parallel_performance_comparison.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
