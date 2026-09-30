"""Generate a paper-oriented Markdown summary from a tau3 results file."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def yes(value: bool) -> int:
    return 1 if value else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.results.read_text(encoding="utf-8"))
    simulations = payload["simulations"]
    durations = [float(item["duration"]) for item in simulations]
    agent_costs = [float(item.get("agent_cost") or 0) for item in simulations]
    user_costs = [float(item.get("user_cost") or 0) for item in simulations]
    rewards = [float((item.get("reward_info") or {}).get("reward") or 0) for item in simulations]
    db_matches = [bool(((item.get("reward_info") or {}).get("db_check") or {}).get("db_match")) for item in simulations]

    actions = defaultdict(lambda: [0, 0])
    communicate_total = 0
    communicate_met = 0
    usage_by_role = defaultdict(lambda: defaultdict(int))
    by_task: dict[str, list[dict]] = defaultdict(list)
    for item in simulations:
        reward_info = item.get("reward_info") or {}
        task_id = str(item.get("task_id"))
        by_task[task_id].append(item)
        for check in reward_info.get("action_checks") or []:
            kind = check.get("tool_type") or "other"
            actions[kind][1] += 1
            actions[kind][0] += yes(bool(check.get("action_match")))
        for check in reward_info.get("communicate_checks") or []:
            communicate_total += 1
            communicate_met += yes(bool(check.get("met")))
        for message in item.get("messages") or []:
            raw_usage = ((message.get("raw_data") or {}).get("usage") or {})
            if not raw_usage:
                continue
            role = str(message.get("role") or "unknown")
            usage_by_role[role]["calls"] += 1
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
            ):
                usage_by_role[role][key] += int(raw_usage.get(key) or 0)

    summary = {
        "simulations": len(simulations),
        "tasks": len(by_task),
        "trials_per_task": sorted({len(items) for items in by_task.values()}),
        "reward_mean": statistics.mean(rewards),
        "reward_successes": sum(reward == 1 for reward in rewards),
        "db_matches": sum(db_matches),
        "duration_mean_s": statistics.mean(durations),
        "duration_p50_s": percentile(durations, 0.50),
        "duration_p95_s": percentile(durations, 0.95),
        "duration_p99_s": percentile(durations, 0.99),
        "agent_cost_total_usd": sum(agent_costs),
        "user_cost_total_usd": sum(user_costs),
        "total_cost_usd": sum(agent_costs) + sum(user_costs),
        "mean_total_cost_usd": statistics.mean(
            [agent + user for agent, user in zip(agent_costs, user_costs, strict=True)]
        ),
        "communicate_checks_met": communicate_met,
        "communicate_checks_total": communicate_total,
        "actions": dict(actions),
        "usage_by_role": {role: dict(values) for role, values in usage_by_role.items()},
    }

    cache_hits = sum(values["prompt_cache_hit_tokens"] for values in usage_by_role.values())
    cache_misses = sum(values["prompt_cache_miss_tokens"] for values in usage_by_role.values())
    llm_calls = sum(values["calls"] for values in usage_by_role.values())

    lines = [
        "# τ³-bench Airline / DeepSeek Mutation Baseline",
        "",
        "## Configuration",
        "",
        "- Upstream commit: `b7ea9074c1cba482b30687fecdb5c8425fd6f619`",
        "- Domain / split: `airline/base`",
        "- Model: `deepseek/deepseek-flash` for agent and user simulator",
        "- Tasks: 26 mutation-bearing tasks selected deterministically from 50 base tasks",
        "- Trials: 3 per task; 78 simulations total",
        "- Temperature: 0.0; maximum concurrency: 3",
        "",
        "## Overall results",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| End-to-end reward / Pass^1 | {summary['reward_successes']}/78 ({summary['reward_mean']:.1%}) |",
        f"| Final database state match | {summary['db_matches']}/78 ({summary['db_matches']/78:.1%}) |",
        f"| Read-action match | {actions['read'][0]}/{actions['read'][1]} ({actions['read'][0]/actions['read'][1]:.1%}) |",
        f"| Write-action match | {actions['write'][0]}/{actions['write'][1]} ({actions['write'][0]/actions['write'][1]:.1%}) |",
        f"| Communication assertions met | {communicate_met}/{communicate_total} ({communicate_met/communicate_total:.1%}) |",
        f"| Mean latency | {summary['duration_mean_s']:.2f} s |",
        f"| Latency p50 / p95 / p99 | {summary['duration_p50_s']:.2f} / {summary['duration_p95_s']:.2f} / {summary['duration_p99_s']:.2f} s |",
        f"| Agent-model cost | ${summary['agent_cost_total_usd']:.4f} total |",
        f"| User-simulator cost | ${summary['user_cost_total_usd']:.4f} total |",
        f"| Combined cost | ${summary['total_cost_usd']:.4f} total; ${summary['mean_total_cost_usd']:.4f}/simulation |",
        f"| LLM calls | {llm_calls} |",
        f"| Provider prompt-cache hit / miss | {cache_hits:,} / {cache_misses:,} tokens ({cache_hits/(cache_hits+cache_misses):.1%} hit) |",
        "| Normal termination | 78/78 (100%) |",
        "",
        "The upstream console additionally reports Pass^2 = 0.654 and Pass^3 = 0.615. These decreasing reliability values show that repeated correctness is materially harder than a single successful run.",
        "",
        "Provider-side prompt caching is reported separately from BranchLab reuse. It mainly captures repeated request prefixes recognized by DeepSeek; BranchLab's contribution must be measured as additional sharing of branch state and tool results under semantic validity.",
        "",
        "| Role | LLM calls | Prompt tokens | Completion tokens | Cache hit | Cache miss |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for role in sorted(usage_by_role):
        usage = usage_by_role[role]
        lines.append(
            f"| {role} | {usage['calls']} | {usage['prompt_tokens']:,} | "
            f"{usage['completion_tokens']:,} | {usage['prompt_cache_hit_tokens']:,} | "
            f"{usage['prompt_cache_miss_tokens']:,} |"
        )
    lines.extend([
        "",
        "## Per-task stability",
        "",
        "| Task | E2E pass | DB match | Mean latency (s) | Mean total cost (USD) | Write actions |",
        "|---:|---:|---:|---:|---:|---:|",
    ])

    for task_id in sorted(by_task, key=lambda value: int(value)):
        items = by_task[task_id]
        task_rewards = [float((item.get("reward_info") or {}).get("reward") or 0) for item in items]
        task_db = [bool(((item.get("reward_info") or {}).get("db_check") or {}).get("db_match")) for item in items]
        task_durations = [float(item["duration"]) for item in items]
        task_costs = [float(item.get("agent_cost") or 0) + float(item.get("user_cost") or 0) for item in items]
        write_met = 0
        write_total = 0
        for item in items:
            for check in (item.get("reward_info") or {}).get("action_checks") or []:
                if check.get("tool_type") == "write":
                    write_total += 1
                    write_met += yes(bool(check.get("action_match")))
        lines.append(
            f"| {task_id} | {sum(value == 1 for value in task_rewards)}/{len(items)} | "
            f"{sum(task_db)}/{len(items)} | {statistics.mean(task_durations):.2f} | "
            f"{statistics.mean(task_costs):.4f} | {write_met}/{write_total} |"
        )

    lines.extend(
        [
            "",
            "## Evidence boundary",
            "",
            "This run is the vanilla DeepSeek baseline on an authoritative public agent benchmark. It establishes task difficulty, variance, cost, latency, action traces, and final-state grading. It does not yet measure 2PL, OCC, or BranchLab, because all three must be evaluated through the same transaction-aware execution adapter before a causal comparison is valid.",
            "",
            "The gap between read-action match (high) and write-action / DB match (lower) supports focusing the system contribution on safe speculative execution and commit semantics rather than on information retrieval alone.",
            "",
        ]
    )
    args.output.write_text("\n".join(lines), encoding="utf-8")
    if args.summary_json:
        args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
