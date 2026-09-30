"""Budget-capped DeepSeek canary for semantic-contract compilation.

Dry-run is the default. API use requires both --execute and --max-api-calls.
The hard cap is three calls so this entry point cannot launch a large batch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from branchlab.deepseek_client import complete_with_usage
from branchlab.semantic_contracts import (
    AUTHORIZATION_PREDICATES,
    HARD_PREDICATES,
    OPERATIONS,
    TOLERATED_CHANGES,
    ContractError,
    SemanticContract,
    compare_contract,
    harden_contract,
    safety_gaps,
)


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "experiments" / "semantic_contract_canary.json"
TRACE_INPUTS = ROOT / "experiments" / "semantic_contract_canary_inputs.json"
RESULTS = ROOT / "results" / "semantic_contract_canary"
SECRET = Path.home() / ".config" / "branchlab" / "deepseek_api_key"
POLICY = ROOT / "external" / "tau2-bench" / "data" / "tau2" / "domains" / "airline" / "policy.md"


def ensure_key() -> None:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return
    if not SECRET.is_file() or (SECRET.stat().st_mode & 0o777) != 0o600:
        raise SystemExit("DeepSeek key missing or secret-file mode is not 600")
    os.environ["DEEPSEEK_API_KEY"] = SECRET.read_text(encoding="utf-8").strip()


def relevant_policy(operation: str, policy: str) -> str:
    common, remainder = policy.split("## Domain Basic", 1)
    sections = {"common": ""}
    current = "common"
    for line in ("## Domain Basic\n" + remainder).splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = line + "\n"
        else:
            sections[current] = sections.get(current, "") + line + "\n"
    wanted = {
        "book_reservation": "book flight",
        "cancel_reservation": "cancel flight",
        "update_reservation_flights": "modify flight",
        "update_reservation_passengers": "modify flight",
        "update_reservation_baggages": "modify flight",
    }[operation]
    return (common + sections.get("domain basic", "") + sections.get(wanted, "")).strip()


def prompt_for_context(
    *, task_id: str, operation: str, context: str, policy: str
) -> list[dict[str, str]]:
    schema = {
        "version": "branchlab.contract.v1",
        "task_id": task_id,
        "operation": f"one of {sorted(OPERATIONS)}",
        "authorization": f"subset of {sorted(AUTHORIZATION_PREDICATES)}",
        "hard_predicates": f"subset of {sorted(HARD_PREDICATES)}",
        "semantic_dependencies": ["dot.separated.state.field"],
        "tolerated_changes": f"subset of {sorted(TOLERATED_CHANGES)}",
        "write_effects": ["dot.separated.field := intended_value"],
        "source_evidence": ["short evidence from dialogue or policy"],
    }
    system = (
        "You compile an Agent transaction into a conservative semantic contract. "
        "Return exactly one JSON object and no prose. Never invent permission. "
        "A missing safety predicate is more serious than an extra conservative predicate."
    )
    user = (
        f"TASK ID: {task_id}\n"
        f"TARGET OPERATION: {operation}\n\n"
        f"USER-VISIBLE DIALOGUE AND TOOL OBSERVATIONS BEFORE THE WRITE:\n{context}\n\n"
        f"RELEVANT AIRLINE POLICY:\n{relevant_policy(operation, policy)}\n\n"
        f"OUTPUT SCHEMA AND CLOSED VOCABULARIES:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def prompt_for(case: dict, policy: str) -> list[dict[str, str]]:
    context = case["user_visible_context"]
    if TRACE_INPUTS.is_file():
        inputs = {item["task_id"]: item for item in json.loads(TRACE_INPUTS.read_text(encoding="utf-8"))}
        if case["task_id"] in inputs:
            context = json.dumps(inputs[case["task_id"]]["messages"], ensure_ascii=False, indent=2)
    return prompt_for_context(
        task_id=case["task_id"],
        operation=case["operation"],
        context=context,
        policy=policy,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-ids", nargs="+", default=["12", "39", "40"])
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--max-output-tokens", type=int, default=800)
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.max_api_calls < 0 or args.max_api_calls > 3:
        raise SystemExit("--max-api-calls must be between 0 and the hard cap of 3")
    if args.max_output_tokens > 1000:
        raise SystemExit("--max-output-tokens exceeds the hard cap of 1000")
    all_cases = json.loads(CASES.read_text(encoding="utf-8"))
    selected = [case for case in all_cases if case["task_id"] in set(args.task_ids)]
    if len(selected) != len(set(args.task_ids)):
        raise SystemExit("unknown or duplicate task id")
    if args.execute and (args.max_api_calls == 0 or len(selected) > args.max_api_calls):
        raise SystemExit("execution requires a positive cap covering every selected task")

    policy = POLICY.read_text(encoding="utf-8")
    RESULTS.mkdir(parents=True, exist_ok=True)
    plans = []
    for case in selected:
        messages = prompt_for(case, policy)
        prompt_text = "\n".join(message["content"] for message in messages)
        output_path = RESULTS / f"task{case['task_id']}.json"
        plans.append(
            {
                "task_id": case["task_id"],
                "operation": case["operation"],
                "prompt_chars": len(prompt_text),
                "prompt_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
                "uses_recorded_trace": TRACE_INPUTS.is_file(),
                "will_call_api": args.execute and not output_path.exists(),
                "output": str(output_path),
            }
        )
        if not args.execute or output_path.exists():
            continue
        ensure_key()
        response = complete_with_usage(
            messages,
            model=args.model,
            temperature=0.0,
            max_tokens=args.max_output_tokens,
        )
        record = {
            "task_id": case["task_id"],
            "model": response.model,
            "usage": response.usage,
            "prompt_sha256": plans[-1]["prompt_sha256"],
            "raw": response.content,
        }
        try:
            predicted = SemanticContract.from_dict(json.loads(response.content))
            expected = SemanticContract.from_dict(case["gold_contract"])
            record["schema_valid"] = True
            record["contract"] = predicted.to_dict()
            record["metrics"] = compare_contract(expected, predicted)
            record["static_safety_gaps"] = safety_gaps(predicted)
            hardened = harden_contract(predicted)
            record["hardened_contract"] = hardened.to_dict()
            record["hardened_metrics"] = compare_contract(expected, hardened)
        except (json.JSONDecodeError, ContractError) as error:
            record["schema_valid"] = False
            record["error"] = str(error)
        output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    plan_path = RESULTS / "plan.json"
    plan_path.write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"execute": args.execute, "planned": plans}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
