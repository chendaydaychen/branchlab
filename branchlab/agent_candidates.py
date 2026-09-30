"""Generate schema-constrained candidate SQL plans for Agent workload collection."""
from __future__ import annotations

import argparse
import json
from .deepseek_client import complete


SYSTEM = """You are a database task planner. Return only valid JSON. Never execute SQL.
Generate diverse candidate read/write plans that comply exactly with the supplied schema.
Each candidate must contain fields: name, shared_reads, private_reads, writes, rationale.
All fields except rationale are arrays of concise SQL statements using only the supplied schema."""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--candidates", type=int, default=4)
    args = parser.parse_args()
    prompt = f"Schema:\n{args.schema}\n\nTask:\n{args.task}\n\nReturn JSON object {{\"candidates\": [...]}} with exactly {args.candidates} candidates."
    text = complete([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
    parsed = json.loads(text)
    if not isinstance(parsed.get("candidates"), list) or len(parsed["candidates"]) != args.candidates:
        raise ValueError("model response does not contain the requested candidate count")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
