"""Aggregate the small semantic-contract canary without additional API calls."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from branchlab.semantic_contracts import SemanticContract, compare_contract, harden_contract, safety_gaps


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "semantic_contract_canary"
CASES = ROOT / "experiments" / "semantic_contract_canary.json"


def main() -> None:
    gold = {
        case["task_id"]: SemanticContract.from_dict(case["gold_contract"])
        for case in json.loads(CASES.read_text(encoding="utf-8"))
    }
    records = []
    for path in sorted(RESULTS.glob("task*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        metrics = record.get("metrics") or {}
        predicted = SemanticContract.from_dict(record["contract"]) if record.get("schema_valid") else None
        static_gaps = record.get("static_safety_gaps") or (safety_gaps(predicted) if predicted else {})
        hardened = record.get("hardened_metrics") or (
            compare_contract(gold[str(record["task_id"])], harden_contract(predicted))
            if predicted else {}
        )
        records.append(
            {
                "task_id": record.get("task_id"),
                "schema_valid": bool(record.get("schema_valid")),
                "operation_exact": bool(metrics.get("operation_exact")),
                "hard_precision": (metrics.get("hard_predicates") or {}).get("precision"),
                "hard_recall": (metrics.get("hard_predicates") or {}).get("recall"),
                "authorization_recall": (metrics.get("authorization") or {}).get("recall"),
                "dangerous_omissions": metrics.get("dangerous_omissions") or [],
                "static_safety_gaps": sorted(
                    (static_gaps.get("authorization") or [])
                    + (static_gaps.get("hard_predicates") or [])
                ),
                "hardened_dangerous_omissions": hardened.get("dangerous_omissions") or [],
                "usage": record.get("usage") or {},
            }
        )
    if not records:
        print("no paid canary results; run the capped experiment first")
        return

    def average(field: str) -> float | None:
        values = [float(row[field]) for row in records if row[field] is not None]
        return mean(values) if values else None

    summary = {
        "tasks": len(records),
        "schema_valid_rate": mean(row["schema_valid"] for row in records),
        "operation_exact_rate": mean(row["operation_exact"] for row in records),
        "mean_hard_precision": average("hard_precision"),
        "mean_hard_recall": average("hard_recall"),
        "mean_authorization_recall": average("authorization_recall"),
        "tasks_with_dangerous_omissions": sum(bool(row["dangerous_omissions"]) for row in records),
        "tasks_rejected_or_hardened_by_static_guard": sum(bool(row["static_safety_gaps"]) for row in records),
        "tasks_with_omissions_after_hardening": sum(bool(row["hardened_dangerous_omissions"]) for row in records),
        "provider_usage": {
            key: sum(int(row["usage"].get(key, 0)) for row in records)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        },
        "records": records,
    }
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Semantic-contract DeepSeek canary",
        "",
        "| task | schema | operation | hard P | hard R | auth R | raw omissions | static guard gaps | after hardening |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in records:
        fmt = lambda value: "-" if value is None else f"{float(value):.3f}"
        lines.append(
            f"| {row['task_id']} | {int(row['schema_valid'])} | {int(row['operation_exact'])} | "
            f"{fmt(row['hard_precision'])} | {fmt(row['hard_recall'])} | "
            f"{fmt(row['authorization_recall'])} | {', '.join(row['dangerous_omissions']) or '-'} | "
            f"{', '.join(row['static_safety_gaps']) or '-'} | "
            f"{', '.join(row['hardened_dangerous_omissions']) or '-'} |"
        )
    lines.extend(
        [
            "",
            f"- Schema-valid rate: {summary['schema_valid_rate']:.3f}",
            f"- Exact-operation rate: {summary['operation_exact_rate']:.3f}",
            f"- Mean hard-predicate recall: {summary['mean_hard_recall']}",
            f"- Tasks with dangerous omissions: {summary['tasks_with_dangerous_omissions']}",
            f"- Tasks caught by static guard: {summary['tasks_rejected_or_hardened_by_static_guard']}",
            f"- Tasks with omissions after hardening: {summary['tasks_with_omissions_after_hardening']}",
            f"- Provider usage: {summary['provider_usage']}",
            "",
            "This three-task run is a canary, not a paper-level aggregate result.",
        ]
    )
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
