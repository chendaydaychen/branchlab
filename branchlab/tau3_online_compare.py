"""Combine online pilot runs with the paired transaction-controller replay."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def online_row(payload: dict) -> dict:
    branches = payload["branch_results"]
    metrics = [branch["transaction_metrics"] for branch in branches]
    return {
        "mode": payload["mode"],
        "successful": sum(branch["reward"] == 1.0 for branch in branches),
        "db_match": sum(branch["db_match"] for branch in branches),
        "branches": len(branches),
        "prefix_messages": payload["prefix"]["messages"],
        "prefix_reads": payload["prefix"]["read_calls"],
        "continuation_reads": sum(item["read_calls"] for item in metrics),
        "physical_reads": payload["aggregate"]["actual_total_physical_reads"],
        "shared_hits": sum(item["shared_read_hits"] for item in metrics),
        "semantic_rebases": sum(item["semantic_rebases"] for item in metrics),
        "mean_continuation_s": mean(branch["duration_s"] for branch in branches),
        "actual_cost_usd": payload["aggregate"]["actual_total_cost_usd"],
    }


def main() -> None:
    online_files = {
        "2pl": "tau3_online_branch_2pl_task11_b3_s710.json",
        "occ": "tau3_online_branch_occ_task11_b3_s710.json",
        "branchlab": "tau3_online_branch_branchlab_task11_b3_s710.json",
    }
    online = {mode: online_row(load(path)) for mode, path in online_files.items()}
    benign = load("tau3_tx_paired_replay.json")["summary"]
    harmful = load("tau3_tx_paired_harmful.json")["summary"]
    payload = {
        "online_normal_path": online,
        "paired_benign": benign,
        "paired_harmful": harmful,
        "interpretation": {
            "online_role": "生态有效性与端到端正确性；轨迹切点不同，不用于系统间性能排序",
            "paired_role": "固定相同78条DeepSeek真实轨迹，隔离事务控制器差异，用于因果比较",
        },
    }

    lines = [
        "# τ³ 三组实验：在线有效性 + 严格配对因果对照",
        "",
        "## 实验解释框架",
        "",
        "在线实验与配对重放回答两个不同问题。在线实验回答三种事务适配器能否在真实 DeepSeek + τ³ 环境中端到端完成任务；严格配对重放让三种协议处理完全相同的 78 条真实 DeepSeek 轨迹，用于比较并发控制决策和读共享。二者不能混为同一个统计样本。",
        "",
        "## A. 在线正常路径 pilot",
        "",
        "| 模式 | 成功/分支 | DB match | 前缀消息 | 前缀读 | continuation逻辑读 | 实际物理读 | 共享命中 | 语义rebase | continuation均值(s) | 实际成本($) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {"2pl": "2PL", "occ": "严格OCC", "branchlab": "BranchLab"}
    for mode in ("2pl", "occ", "branchlab"):
        row = online[mode]
        lines.append(
            f"| {labels[mode]} | {row['successful']}/{row['branches']} | "
            f"{row['db_match']}/{row['branches']} | {row['prefix_messages']} | "
            f"{row['prefix_reads']} | {row['continuation_reads']} | {row['physical_reads']} | "
            f"{row['shared_hits']} | {row['semantic_rebases']} | "
            f"{row['mean_continuation_s']:.2f} | {row['actual_cost_usd']:.4f} |"
        )
    lines.extend(
        [
            "",
            "三组均为 3/3 成功且 DB 状态完全匹配，说明实现均可端到端运行。由于相同 `prefix-reads=4` 在随机对话中落在不同语义位置，且公共前缀调度也提供给了 2PL/OCC，这张表不能用于宣称 BranchLab 的时延或读次数优于完整的传统基线；它是组件级正常路径 sanity check。",
            "",
            "## B. 同轨迹、同扰动的严格配对结果",
            "",
            "### 良性并发变化",
            "",
            "| 模式 | 可写轨迹 | 接受 | 拒绝 | 阻塞变化 | 物理读 | 共享命中 | 语义rebase |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for mode in ("2pl", "occ", "branchlab"):
        row = benign[mode]
        lines.append(
            f"| {labels[mode]} | {row['write_bearing_traces']} | {row['transaction_accepted']} | "
            f"{row['transaction_rejected']} | {row['disturbances_blocked']} | {row['physical_reads']} | "
            f"{row['shared_read_hits']} | {row['semantic_rebases']} |"
        )
    lines.extend(
        [
            "",
            "严格 OCC 对 71/71 个语义无害变化全部拒绝；2PL 通过锁阻止 71/71 个变化；BranchLab 不阻塞变化并接受 71/71 个安全提交。相对 2PL，BranchLab 的物理读从 642 降至 252，减少 60.7%。",
            "",
            "### 有害并发变化",
            "",
            "| 模式 | 可写轨迹 | 接受 | 拒绝 | 阻塞变化 | 物理读 | 共享命中 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for mode in ("2pl", "occ", "branchlab"):
        row = harmful[mode]
        lines.append(
            f"| {labels[mode]} | {row['write_bearing_traces']} | {row['transaction_accepted']} | "
            f"{row['transaction_rejected']} | {row['disturbances_blocked']} | {row['physical_reads']} | "
            f"{row['shared_read_hits']} |"
        )
    lines.extend(
        [
            "",
            "在 71 个有害变化中，BranchLab 与严格 OCC 都拒绝 71/71，BranchLab 错误接受为 0；2PL 则通过锁使变化无法进入，因此其 71 个接受均是在受锁保护的旧状态上安全完成。",
            "",
            "## 当前可支持的论文表述",
            "",
            "> 在真实 τ³/DeepSeek 轨迹上，BranchLab 在不阻止良性并发变化的情况下接受全部 71 个安全提交，并拒绝全部 71 个有害提交；相同条件下严格 OCC 对良性变化产生 100% 假拒绝，而 2PL 需要阻塞所有变化。跨分支前缀/读共享使物理读相对 2PL 减少 60.7%。此外，在线三分支 pilot 中三个候选均完成任务且数据库终态正确，证明该机制可集成进真实 LLM Agent 执行链路。",
            "",
            "## 仍缺少的主实验",
            "",
            "1. 自动语义切点，而不是固定读次数。",
            "2. 不给传统 2PL/OCC 前缀共享的完整系统基线。",
            "3. 真实并行调度与 2PL 锁等待、OCC abort/retry 的端到端时间。",
            "4. 至少 5 个种子、多个 τ³ 写任务及置信区间。",
            "5. 完整方案与 no-share、strict-validation、no-range-rebase 消融。",
            "",
        ]
    )
    (RESULTS / "tau3_three_way_online_and_paired.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (RESULTS / "tau3_three_way_online_and_paired.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
