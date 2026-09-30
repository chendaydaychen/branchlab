"""Measure branch-prefix and tool-result reuse opportunities in tau3 traces."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


WRITE_TOOLS = {
    "book_reservation",
    "cancel_reservation",
    "update_reservation_flights",
    "update_reservation_baggages",
    "update_reservation_passengers",
}


def canonical_call(call: dict[str, Any]) -> tuple[str, str]:
    function = call.get("function") or {}
    name = call.get("name") or function.get("name") or "unknown"
    arguments = call.get("arguments", function.get("arguments", {}))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            pass
    return name, json.dumps(arguments, sort_keys=True, separators=(",", ":"))


def trace_calls(simulation: dict[str, Any]) -> list[tuple[str, str]]:
    result = []
    for message in simulation.get("messages") or []:
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict):
                result.append(canonical_call(call))
    return result


def common_prefix_length(traces: list[list[tuple[str, str]]]) -> int:
    if not traces:
        return 0
    length = 0
    for calls in zip(*traces):
        if len(set(calls)) != 1:
            break
        length += 1
    return length


def trie_nodes(traces: list[list[tuple[str, str]]]) -> int:
    root: dict = {}
    nodes = 0
    for trace in traces:
        cursor = root
        for call in trace:
            if call not in cursor:
                cursor[call] = {}
                nodes += 1
            cursor = cursor[call]
    return nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.results.read_text(encoding="utf-8"))
    by_task: dict[str, list[list[tuple[str, str]]]] = defaultdict(list)
    for simulation in payload["simulations"]:
        by_task[str(simulation["task_id"])].append(trace_calls(simulation))

    rows = []
    for task_id, traces in by_task.items():
        total = sum(map(len, traces))
        nodes = trie_nodes(traces)
        prefix = common_prefix_length(traces)
        all_reads = [call for trace in traces for call in trace if call[0] not in WRITE_TOOLS]
        distinct_reads = len(set(all_reads))
        rows.append(
            {
                "task_id": task_id,
                "trace_lengths": [len(trace) for trace in traces],
                "common_prefix_calls": prefix,
                "total_calls": total,
                "trie_nodes": nodes,
                "prefix_shareable_calls": total - nodes,
                "read_calls": len(all_reads),
                "distinct_read_calls": distinct_reads,
                "memoizable_read_calls": len(all_reads) - distinct_reads,
            }
        )

    total_calls = sum(row["total_calls"] for row in rows)
    trie_nodes_total = sum(row["trie_nodes"] for row in rows)
    read_calls = sum(row["read_calls"] for row in rows)
    distinct_reads = sum(row["distinct_read_calls"] for row in rows)
    summary = {
        "tasks": len(rows),
        "trials_per_task": 3,
        "total_tool_calls": total_calls,
        "prefix_trie_nodes": trie_nodes_total,
        "prefix_shareable_calls": total_calls - trie_nodes_total,
        "prefix_shareable_fraction": (total_calls - trie_nodes_total) / total_calls,
        "tasks_with_nonempty_common_prefix": sum(row["common_prefix_calls"] > 0 for row in rows),
        "mean_common_prefix_calls": statistics.mean(row["common_prefix_calls"] for row in rows),
        "read_calls": read_calls,
        "distinct_read_calls_within_task": distinct_reads,
        "memoizable_read_calls": read_calls - distinct_reads,
        "memoizable_read_fraction": (read_calls - distinct_reads) / read_calls,
    }

    lines = [
        "# τ³-bench Multi-branch Prefix Opportunity",
        "",
        "Each task's three independent DeepSeek trials is treated as three candidate execution branches. Calls are identical only when both the tool name and canonicalized arguments match.",
        "",
        "## Aggregate",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Tasks / traces | {len(rows)} / {len(rows) * 3} |",
        f"| Actual tool calls | {total_calls} |",
        f"| Nodes after exact prefix-trie sharing | {trie_nodes_total} |",
        f"| Calls removable by prefix sharing | {total_calls - trie_nodes_total} ({(total_calls-trie_nodes_total)/total_calls:.1%}) |",
        f"| Tasks with a common three-branch prefix | {summary['tasks_with_nonempty_common_prefix']}/{len(rows)} ({summary['tasks_with_nonempty_common_prefix']/len(rows):.1%}) |",
        f"| Mean common prefix length | {summary['mean_common_prefix_calls']:.2f} calls |",
        f"| Read calls | {read_calls} |",
        f"| Repeated exact reads within a task | {read_calls - distinct_reads} ({(read_calls-distinct_reads)/read_calls:.1%}) |",
        "",
        "Prefix-trie savings are conservative: calls after branches diverge are not merged even if they later become identical. Exact-read memoization is an upper bound because a cached result is reusable only while its semantic dependencies remain valid.",
        "",
        "## Per task",
        "",
        "| Task | Trace lengths | Common prefix | Prefix-shareable | Repeated reads |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: int(item["task_id"])):
        lines.append(
            f"| {row['task_id']} | {'/'.join(map(str, row['trace_lengths']))} | "
            f"{row['common_prefix_calls']} | {row['prefix_shareable_calls']} | "
            f"{row['memoizable_read_calls']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This analysis establishes that shared work exists in real public Agent trajectories. It does not claim the full theoretical savings are realized: the runtime experiment must measure cache lookup overhead, invalidation, semantic validation, and LLM-prefix reuse separately.",
            "",
        ]
    )
    args.output.write_text("\n".join(lines), encoding="utf-8")
    if args.summary_json:
        args.summary_json.write_text(json.dumps({"summary": summary, "tasks": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
