"""Run independent tau3 conversations concurrently as a no-share baseline."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tau2.domains.airline.environment import get_tasks
from tau2.runner.simulation import run_simulation

from branchlab.tau3_online_branch import build_orchestrator, ensure_key
from branchlab.tau3_tx_environment import SharedReadCache


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("2pl", "occ"), required=True)
    parser.add_argument("--task-id", default="11")
    parser.add_argument("--model", default="deepseek/deepseek-flash")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=720)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args()
    ensure_key()
    task = next(task for task in get_tasks("base") if str(task.id) == args.task_id)

    def run_one(index: int):
        seed = args.seed + index + 1
        # A distinct cache and a fresh environment per run: there is no state,
        # message, tool-result, or prefix sharing between baseline executions.
        orchestrator, environment = build_orchestrator(
            task=task.model_copy(deep=True),
            mode=args.mode,
            model=args.model,
            temperature=args.temperature,
            seed=seed,
            shared_cache=SharedReadCache(),
        )
        simulation = run_simulation(orchestrator)
        return {
            "run": index + 1,
            "seed": seed,
            "reward": float(simulation.reward_info.reward or 0.0),
            "db_match": bool(simulation.reward_info.db_check.db_match),
            "duration_s": float(simulation.duration or 0.0),
            "cost_usd": float(simulation.agent_cost or 0.0)
            + float(simulation.user_cost or 0.0),
            "transaction_metrics": environment.metrics_dict(),
            "simulation": simulation.model_dump(mode="json"),
        }

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.runs) as executor:
        futures = [executor.submit(run_one, index) for index in range(args.runs)]
        runs = [future.result() for future in as_completed(futures)]
    wallclock = time.perf_counter() - started
    runs.sort(key=lambda item: item["run"])
    payload = {
        "kind": "independent-no-share-parallel",
        "mode": args.mode,
        "task_id": args.task_id,
        "model": args.model,
        "temperature": args.temperature,
        "base_seed": args.seed,
        "runs": runs,
        "aggregate": {
            "successful_runs": sum(item["reward"] == 1.0 for item in runs),
            "db_match_runs": sum(item["db_match"] for item in runs),
            "wallclock_s": wallclock,
            "total_cost_usd": sum(item["cost_usd"] for item in runs),
            "logical_reads": sum(
                item["transaction_metrics"]["read_calls"] for item in runs
            ),
            "physical_reads": sum(
                item["transaction_metrics"]["physical_reads"] for item in runs
            ),
            "shared_read_hits": sum(
                item["transaction_metrics"]["shared_read_hits"] for item in runs
            ),
        },
    }
    stem = f"tau3_independent_parallel_{args.mode}_task{args.task_id}_r{args.runs}_s{args.seed}"
    path = ROOT / "results" / f"{stem}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({**payload, "runs": [
        {key: value for key, value in item.items() if key != "simulation"}
        for item in runs
    ]}, indent=2, ensure_ascii=False))
    print(f"result: {path}")


if __name__ == "__main__":
    main()
