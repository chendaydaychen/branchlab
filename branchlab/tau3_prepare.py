"""Select state-mutating τ³-bench airline tasks for BranchLab evaluation."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAU_ROOT = ROOT / "external" / "tau2-bench"
DATA = TAU_ROOT / "data" / "tau2" / "domains" / "airline"

WRITE_TOOLS = {
    "book_reservation",
    "cancel_reservation",
    "send_certificate",
    "update_reservation_baggages",
    "update_reservation_flights",
    "update_reservation_passengers",
}
READ_TOOLS = {
    "get_reservation_details",
    "get_user_details",
    "list_all_airports",
    "search_direct_flight",
    "search_onestop_flight",
    "get_flight_status",
    "calculate",
}


def main() -> None:
    tasks = json.loads((DATA / "tasks.json").read_text())
    splits = json.loads((DATA / "split_tasks.json").read_text())
    by_id = {str(task["id"]): task for task in tasks}
    selected = []
    for task_id in splits["base"]:
        task = by_id[str(task_id)]
        actions = task["evaluation_criteria"]["actions"]
        names = [action["name"] for action in actions]
        writes = [name for name in names if name in WRITE_TOOLS]
        if not writes:
            continue
        selected.append(
            {
                "id": str(task_id),
                "purpose": task["description"]["purpose"],
                "expected_actions": names,
                "write_actions": writes,
                "read_prefix_actions": [name for name in names if name in READ_TOOLS],
                "reason_for_call": task["user_scenario"]["instructions"]["reason_for_call"],
            }
        )
    summary = {
        "benchmark": "tau3-bench",
        "repository_commit": "b7ea9074c1cba482b30687fecdb5c8425fd6f619",
        "domain": "airline",
        "base_task_count": len(splits["base"]),
        "mutating_task_count": len(selected),
        "write_action_counts": dict(Counter(write for row in selected for write in row["write_actions"])),
        "task_ids": [row["id"] for row in selected],
        "tasks": selected,
    }
    out = ROOT / "results" / "tau3_airline_mutating_tasks.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in summary.items() if key != "tasks"}, indent=2))
    print(out)


if __name__ == "__main__":
    main()
