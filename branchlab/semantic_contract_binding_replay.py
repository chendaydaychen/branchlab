"""Verify that contracts cannot be replayed across branches, snapshots, or writes."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from branchlab.semantic_contracts import SemanticContract, compile_contract


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "experiments" / "semantic_contract_canary.json"
INPUTS = ROOT / "experiments" / "semantic_contract_canary_inputs.json"
OUT_JSON = ROOT / "results" / "semantic_contract_binding_replay.json"
OUT_MD = ROOT / "results" / "semantic_contract_binding_replay.md"


def mutate(arguments: dict) -> dict:
    changed = deepcopy(arguments)
    key = sorted(changed)[0]
    value = changed[key]
    if isinstance(value, bool):
        changed[key] = not value
    elif isinstance(value, (int, float)):
        changed[key] = value + 1
    elif isinstance(value, str):
        changed[key] = value + "__changed"
    elif isinstance(value, list):
        changed[key] = value + [{"changed": True}]
    elif isinstance(value, dict):
        changed[key] = value | {"changed": True}
    else:
        changed[key] = "changed"
    return changed


def main() -> None:
    cases = {case["task_id"]: case for case in json.loads(CASES.read_text(encoding="utf-8"))}
    inputs = json.loads(INPUTS.read_text(encoding="utf-8"))
    rows = []
    for item in inputs:
        task_id = item["task_id"]
        semantic = SemanticContract.from_dict(cases[task_id]["gold_contract"])
        write = item["target_write"]
        compiled = compile_contract(
            semantic,
            branch_id=f"task-{task_id}/candidate-0",
            snapshot_id=item["context_sha256"],
            operation=write["operation"],
            arguments=write["arguments"],
        )
        checks = {
            "exact": compiled.authorizes(
                branch_id=f"task-{task_id}/candidate-0",
                snapshot_id=item["context_sha256"],
                operation=write["operation"],
                arguments=write["arguments"],
            ),
            "wrong_branch": compiled.authorizes(
                branch_id=f"task-{task_id}/candidate-1",
                snapshot_id=item["context_sha256"],
                operation=write["operation"],
                arguments=write["arguments"],
            ),
            "wrong_snapshot": compiled.authorizes(
                branch_id=f"task-{task_id}/candidate-0",
                snapshot_id=item["context_sha256"] + "changed",
                operation=write["operation"],
                arguments=write["arguments"],
            ),
            "changed_write": compiled.authorizes(
                branch_id=f"task-{task_id}/candidate-0",
                snapshot_id=item["context_sha256"],
                operation=write["operation"],
                arguments=mutate(write["arguments"]),
            ),
        }
        rows.append(
            {
                "task_id": task_id,
                "operation": write["operation"],
                "exact_accepted": checks["exact"][0],
                "wrong_branch_rejected": not checks["wrong_branch"][0],
                "wrong_snapshot_rejected": not checks["wrong_snapshot"][0],
                "changed_write_rejected": not checks["changed_write"][0],
                "reasons": {key: value[1] for key, value in checks.items()},
            }
        )
    summary = {
        "contracts": len(rows),
        "exact_accepted": sum(row["exact_accepted"] for row in rows),
        "wrong_branch_rejected": sum(row["wrong_branch_rejected"] for row in rows),
        "wrong_snapshot_rejected": sum(row["wrong_snapshot_rejected"] for row in rows),
        "changed_write_rejected": sum(row["changed_write_rejected"] for row in rows),
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Semantic-contract binding replay",
        "",
        "| task | operation | exact accepted | wrong branch rejected | wrong snapshot rejected | changed write rejected |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task_id']} | {row['operation']} | {int(row['exact_accepted'])} | "
            f"{int(row['wrong_branch_rejected'])} | {int(row['wrong_snapshot_rejected'])} | "
            f"{int(row['changed_write_rejected'])} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, indent=2))


if __name__ == "__main__":
    main()
