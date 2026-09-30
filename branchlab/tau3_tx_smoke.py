"""Run one real tau3 simulation through the transaction-aware environment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tau2.domains.airline.environment import get_environment, get_tasks
from tau2.orchestrator.orchestrator import Orchestrator
from tau2.runner.build import build_agent, build_user
from tau2.runner.simulation import run_simulation

from branchlab.tau3_tx_environment import TransactionalEnvironment


ROOT = Path(__file__).resolve().parents[1]


def ensure_key() -> None:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return
    secret = Path.home() / ".config" / "branchlab" / "deepseek_api_key"
    if not secret.is_file() or (secret.stat().st_mode & 0o777) != 0o600:
        raise SystemExit("DeepSeek key missing or secret-file mode is not 600")
    os.environ["DEEPSEEK_API_KEY"] = secret.read_text(encoding="utf-8").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("2pl", "occ", "branchlab"), required=True)
    parser.add_argument("--task-id", default="11")
    parser.add_argument("--model", default="deepseek/deepseek-flash")
    parser.add_argument("--seed", type=int, default=300)
    args = parser.parse_args()
    ensure_key()

    task = next(task for task in get_tasks("base") if str(task.id) == args.task_id)
    environment = TransactionalEnvironment(get_environment(), args.mode)
    llm_args = {"temperature": 0.0}
    agent = build_agent(
        "llm_agent", environment, llm=args.model, llm_args=llm_args, task=task
    )
    user = build_user(
        "user_simulator", environment, task, llm=args.model, llm_args=llm_args
    )
    orchestrator = Orchestrator(
        domain="airline",
        agent=agent,
        user=user,
        environment=environment,
        task=task,
        max_steps=100,
        max_errors=10,
        seed=args.seed,
        timeout=900,
    )
    simulation = run_simulation(orchestrator)
    output = {
        "mode": args.mode,
        "task_id": args.task_id,
        "seed": args.seed,
        "model": args.model,
        "reward": simulation.reward_info.reward,
        "db_match": simulation.reward_info.db_check.db_match,
        "duration_s": simulation.duration,
        "agent_cost_usd": simulation.agent_cost,
        "user_cost_usd": simulation.user_cost,
        "termination_reason": str(simulation.termination_reason),
        "transaction_metrics": environment.metrics_dict(),
        "simulation": simulation.model_dump(mode="json"),
    }
    path = ROOT / "results" / f"tau3_tx_{args.mode}_task{args.task_id}_s{args.seed}.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key != "simulation"}, indent=2))
    print(f"result: {path}")


if __name__ == "__main__":
    main()
