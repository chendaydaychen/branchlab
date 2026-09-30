"""Paired replay of real tau3 traces under 2PL, OCC, and BranchLab."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

from tau2.data_model.message import ToolCall
from tau2.data_model.tasks import Task
from tau2.domains.airline.environment import get_environment

from branchlab.tau3_tx_environment import SharedReadCache, TransactionalEnvironment


MODES = ("2pl", "occ", "branchlab")


def iter_tool_calls(simulation: dict[str, Any]):
    for message in simulation.get("messages") or []:
        for raw in message.get("tool_calls") or []:
            if isinstance(raw, dict):
                yield ToolCall.model_validate(raw)


def initialize(environment: TransactionalEnvironment, task: Task) -> None:
    initial = task.initial_state
    environment.set_state(
        initialization_data=initial.initialization_data if initial else None,
        initialization_actions=initial.initialization_actions if initial else None,
        message_history=initial.message_history if initial and initial.message_history else [],
    )


def replay_one(
    mode: str,
    task: Task,
    simulation: dict[str, Any],
    shared_cache: SharedReadCache | None = None,
    disturbance_kind: str = "benign",
) -> dict[str, Any]:
    environment = TransactionalEnvironment(
        get_environment(), mode, shared_cache=shared_cache
    )
    initialize(environment, task)
    writes = 0
    upstream_errors = 0
    transaction_conflicts = 0
    conflict_reasons = []
    disturbance = "not-attempted"
    disturbed = False

    for call in iter_tool_calls(simulation):
        is_write = environment.inner._is_mutating_tool(call.name)
        if is_write and not disturbed:
            if disturbance_kind == "benign":
                _, disturbance = environment.inject_benign_disturbance()
            else:
                _, disturbance = environment.inject_harmful_disturbance(call)
            disturbed = True
        response = environment.get_response(call)
        if is_write:
            writes += 1
        if response.error:
            if "TransactionConflict" in response.content:
                transaction_conflicts += 1
                conflict_reasons.append(response.content)
                break
            upstream_errors += 1

    return {
        "mode": mode,
        "task_id": str(task.id),
        "trial": simulation.get("trial"),
        "writes": writes,
        "disturbance": disturbance,
        "transaction_accepted": writes > 0 and transaction_conflicts == 0,
        "transaction_conflicts": transaction_conflicts,
        "conflict_reasons": conflict_reasons,
        "upstream_tool_errors": upstream_errors,
        "metrics": environment.metrics_dict(),
    }


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("output_markdown", type=Path)
    parser.add_argument(
        "--disturbance", choices=("benign", "harmful"), default="benign"
    )
    args = parser.parse_args()

    payload = json.loads(args.results.read_text(encoding="utf-8"))
    tasks = {str(raw["id"]): Task.model_validate(raw) for raw in payload["tasks"]}
    rows = []
    branch_caches = defaultdict(SharedReadCache)
    for simulation in payload["simulations"]:
        task_id = str(simulation["task_id"])
        task = tasks[task_id]
        for mode in MODES:
            cache = branch_caches[task_id] if mode == "branchlab" else None
            rows.append(
                replay_one(
                    mode,
                    task,
                    simulation,
                    cache,
                    disturbance_kind=args.disturbance,
                )
            )

    summaries = {}
    for mode in MODES:
        selected = [row for row in rows if row["mode"] == mode]
        write_bearing = [row for row in selected if row["writes"] > 0]
        injected = [
            row
            for row in write_bearing
            if row["disturbance"] not in {"not-attempted", "no-observed-mutable-resource"}
        ]
        summaries[mode] = {
            "traces": len(selected),
            "write_bearing_traces": len(write_bearing),
            "disturbance_covered_traces": len(injected),
            "transaction_accepted": sum(row["transaction_accepted"] for row in injected),
            "transaction_rejected": sum(not row["transaction_accepted"] for row in injected),
            "physical_reads": sum(row["metrics"]["physical_reads"] for row in selected),
            "shared_read_hits": sum(row["metrics"]["shared_read_hits"] for row in selected),
            "validation_failures": sum(row["metrics"]["validation_failures"] for row in selected),
            "semantic_rebases": sum(row["metrics"]["semantic_rebases"] for row in selected),
            "disturbances_applied": sum(row["metrics"]["disturbances_applied"] for row in selected),
            "disturbances_blocked": sum(row["metrics"]["disturbances_blocked"] for row in selected),
        }

    output = {
        "source": str(args.results),
        "disturbance": args.disturbance,
        "summary": summaries,
        "runs": rows,
    }
    args.output_json.write_text(json.dumps(output, indent=2), encoding="utf-8")

    covered = min(summaries[mode]["disturbance_covered_traces"] for mode in MODES)
    lines = [
        "# τ³-bench Paired Transaction Replay",
        "",
        f"The exact same 78 recorded DeepSeek trajectories are replayed through all three controllers. Immediately before the first write, the harness attempts one {args.disturbance} concurrent change. 2PL blocks the change; OCC and BranchLab receive the identical changed state.",
        "",
        "## Results",
        "",
        "| Mode | Covered write traces | Accepted | Rejected | Applied / blocked disturbances | Physical reads | Shared-read hits | Semantic rebases |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode in MODES:
        item = summaries[mode]
        lines.append(
            f"| {mode} | {item['disturbance_covered_traces']} | "
            f"{item['transaction_accepted']} | {item['transaction_rejected']} | "
            f"{item['disturbances_applied']} / {item['disturbances_blocked']} | "
            f"{item['physical_reads']} | {item['shared_read_hits']} | "
            f"{item['semantic_rebases']} |"
        )
    lines.extend(
        [
            "",
            (
                f"The paired comparison has {covered} common disturbance-covered traces. "
                + (
                    "Rejections in this experiment are false rejections because every injected change preserves the pending write's task predicates."
                    if args.disturbance == "benign"
                    else "Every applied disturbance violates a hard predicate, so an accepted transaction would be a false acceptance."
                )
            ),
            "",
            "## Interpretation boundary",
            "",
            "This is deterministic trace replay over real τ³ tool trajectories. It removes LLM sampling variance and tests transaction acceptance and reuse logic against the actual public workload. It does not measure lock-wait wall time or online multi-branch LLM scheduling; those require the live concurrent runner.",
            "",
        ]
    )
    args.output_markdown.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
