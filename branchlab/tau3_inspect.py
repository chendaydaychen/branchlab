"""Print a compact, credential-free summary of a tau3 results.json file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--dialogue", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.results.read_text(encoding="utf-8"))
    for simulation in payload["simulations"]:
        reward = simulation.get("reward_info") or {}
        print(
            json.dumps(
                {
                    "task_id": simulation.get("task_id"),
                    "trial": simulation.get("trial"),
                    "duration_s": simulation.get("duration"),
                    "termination": simulation.get("termination_reason"),
                    "agent_cost_usd": simulation.get("agent_cost"),
                    "user_cost_usd": simulation.get("user_cost"),
                    "reward": reward.get("reward"),
                    "db_match": (reward.get("db_check") or {}).get("db_match"),
                    "action_reward": reward.get("action_reward"),
                    "communicate_checks": reward.get("communicate_checks"),
                },
                ensure_ascii=False,
            )
        )
        if not args.dialogue:
            continue
        for index, message in enumerate(simulation.get("messages") or []):
            content = " ".join((message.get("content") or "").split())
            calls = []
            for call in message.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                function = call.get("function") or {}
                calls.append(call.get("name") or function.get("name") or "unknown")
            suffix = f" [tools: {', '.join(calls)}]" if calls else ""
            print(f"  {index:02d} {message.get('role')}: {content[:800]}{suffix}")


if __name__ == "__main__":
    main()
