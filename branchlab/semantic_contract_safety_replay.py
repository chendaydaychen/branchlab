"""Deterministically mutate gold contracts and test the trusted safety guard."""

from __future__ import annotations

import json
from pathlib import Path

from branchlab.semantic_contracts import (
    MINIMUM_AUTHORIZATION,
    MINIMUM_HARD_PREDICATES,
    SemanticContract,
    harden_contract,
    safety_gaps,
)


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "experiments" / "semantic_contract_canary.json"
OUT_JSON = ROOT / "results" / "semantic_contract_safety_replay.json"
OUT_MD = ROOT / "results" / "semantic_contract_safety_replay.md"


def main() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    trials = []
    for case in cases:
        gold = SemanticContract.from_dict(case["gold_contract"])
        mandatory = {
            "authorization": sorted(MINIMUM_AUTHORIZATION & set(gold.authorization)),
            "hard_predicates": sorted(
                MINIMUM_HARD_PREDICATES[gold.operation] & set(gold.hard_predicates)
            ),
        }
        for field, identifiers in mandatory.items():
            for identifier in identifiers:
                value = gold.to_dict()
                value[field].remove(identifier)
                mutated = SemanticContract.from_dict(value)
                gaps = safety_gaps(mutated)
                hardened = harden_contract(mutated)
                trials.append(
                    {
                        "task_id": gold.task_id,
                        "operation": gold.operation,
                        "field": field,
                        "removed": identifier,
                        "detected": identifier in gaps[field],
                        "restored": identifier in getattr(hardened, field),
                        "safe_after_hardening": not any(safety_gaps(hardened).values()),
                    }
                )
    summary = {
        "contracts": len(cases),
        "mutation_trials": len(trials),
        "detected": sum(trial["detected"] for trial in trials),
        "restored": sum(trial["restored"] for trial in trials),
        "safe_after_hardening": sum(trial["safe_after_hardening"] for trial in trials),
        "failures": [
            trial
            for trial in trials
            if not (trial["detected"] and trial["restored"] and trial["safe_after_hardening"])
        ],
        "trials": trials,
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Semantic-contract static safety replay",
        "",
        f"- Gold contracts: {summary['contracts']}",
        f"- Single-omission mutation trials: {summary['mutation_trials']}",
        f"- Omissions detected: {summary['detected']}/{summary['mutation_trials']}",
        f"- Predicates restored: {summary['restored']}/{summary['mutation_trials']}",
        f"- Safe after hardening: {summary['safe_after_hardening']}/{summary['mutation_trials']}",
        f"- Failures: {len(summary['failures'])}",
        "",
        "Each trial removes one mandatory authorization or hard predicate from a valid contract. This is a deterministic guard test, not an LLM-quality result.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "trials"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
