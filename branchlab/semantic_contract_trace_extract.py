"""Extract pre-write, user-visible contexts from already recorded tau3 traces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "experiments" / "semantic_contract_canary.json"
OUTPUT = ROOT / "experiments" / "semantic_contract_canary_inputs.json"
ARTIFACTS = (
    ROOT
    / "external"
    / "tau2-bench"
    / "data"
    / "simulations"
    / "branchlab_deepseek_mutating"
    / "artifacts"
)


def tool_names(response: dict[str, Any]) -> list[str]:
    names = []
    for call in response.get("tool_calls") or []:
        names.append(call.get("name") or (call.get("function") or {}).get("name"))
    return [name for name in names if name]


def normalize_content(content: Any) -> Any:
    if isinstance(content, (str, int, float, bool)) or content is None:
        return content
    return json.loads(json.dumps(content, ensure_ascii=False, default=str))


def extract(case: dict[str, Any]) -> dict[str, Any]:
    task_root = ARTIFACTS / f"task_{case['task_id']}"
    for simulation in sorted(task_root.glob("sim_*")):
        debug = simulation / "llm_debug"
        for path in sorted(debug.glob("*agent_response*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if case["operation"] not in tool_names(record.get("response") or {}):
                continue
            matching_calls = [
                call
                for call in record.get("response", {}).get("tool_calls") or []
                if (call.get("name") or (call.get("function") or {}).get("name"))
                == case["operation"]
            ]
            target = matching_calls[0]
            target_name = target.get("name") or target["function"]["name"]
            target_arguments = target.get("arguments")
            if target_arguments is None:
                target_arguments = target["function"].get("arguments", {})
            if isinstance(target_arguments, str):
                target_arguments = json.loads(target_arguments)
            messages = [
                {
                    "role": message.get("role"),
                    "content": normalize_content(message.get("content")),
                }
                for message in record["request"]["messages"]
                if message.get("role") != "system"
            ]
            serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True)
            return {
                "task_id": case["task_id"],
                "operation": case["operation"],
                "source_trace": str(path.relative_to(ROOT)),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "context_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
                "target_write": {
                    "operation": target_name,
                    "arguments": target_arguments,
                },
                "messages": messages,
            }
    raise RuntimeError(f"no recorded write trace for task {case['task_id']}")


def main() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    extracted = [extract(case) for case in cases]
    OUTPUT.write_text(json.dumps(extracted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    "task_id": item["task_id"],
                    "operation": item["operation"],
                    "messages": len(item["messages"]),
                    "source_trace": item["source_trace"],
                }
                for item in extracted
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
