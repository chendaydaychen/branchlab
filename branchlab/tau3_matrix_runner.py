"""Resumable multi-task, multi-seed online performance matrix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
LOGS = RESULTS / "matrix_logs"
CHECKPOINT = RESULTS / "tau3_performance_matrix_checkpoint.json"


def load_checkpoint() -> dict:
    if CHECKPOINT.is_file():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {"runs": {}}


def save_checkpoint(checkpoint: dict) -> None:
    CHECKPOINT.write_text(
        json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def expected_result(mode: str, task: str, seed: int, candidates: int) -> Path:
    if mode == "branchlab":
        name = f"tau3_online_branch_branchlab_task{task}_b{candidates}_s{seed}.json"
    else:
        name = f"tau3_independent_parallel_{mode}_task{task}_r{candidates}_s{seed}.json"
    return RESULTS / name


def valid_result(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except (OSError, json.JSONDecodeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="+", default=["7", "11", "12", "20", "40"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[800])
    parser.add_argument("--modes", nargs="+", choices=("2pl", "occ", "branchlab"), default=["2pl", "occ", "branchlab"])
    parser.add_argument("--candidates", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--model", default="deepseek/deepseek-flash")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="actually call the online model; otherwise print a zero-cost plan",
    )
    parser.add_argument(
        "--max-new-runs",
        type=int,
        default=0,
        help="hard budget cap for new online configurations",
    )
    args = parser.parse_args()

    if args.max_new_runs < 0:
        raise SystemExit("--max-new-runs must be non-negative")

    LOGS.mkdir(parents=True, exist_ok=True)
    checkpoint = load_checkpoint()
    checkpoint["config"] = {
        "tasks": args.tasks,
        "seeds": args.seeds,
        "modes": args.modes,
        "candidates": args.candidates,
        "temperature": args.temperature,
        "model": args.model,
    }
    save_checkpoint(checkpoint)

    total = len(args.tasks) * len(args.seeds) * len(args.modes)
    missing = sum(
        not valid_result(expected_result(mode, task, seed, args.candidates))
        for task in args.tasks
        for seed in args.seeds
        for mode in args.modes
    )
    print(
        f"matrix plan: total={total}, existing={total - missing}, new={missing}, "
        f"execute={args.execute}, max_new_runs={args.max_new_runs}",
        flush=True,
    )
    if not args.execute:
        print("dry-run only; pass --execute with a positive --max-new-runs", flush=True)
        return
    if args.max_new_runs == 0:
        raise SystemExit("online execution requires --max-new-runs > 0")

    position = 0
    new_runs = 0
    for task in args.tasks:
        for seed in args.seeds:
            for mode in args.modes:
                position += 1
                key = f"task{task}/seed{seed}/{mode}"
                result_path = expected_result(mode, task, seed, args.candidates)
                previous = checkpoint["runs"].get(key, {})
                if valid_result(result_path):
                    checkpoint["runs"][key] = {
                        "status": "complete",
                        "result": str(result_path),
                        "reused": True,
                    }
                    save_checkpoint(checkpoint)
                    print(f"[{position}/{total}] reuse {key}", flush=True)
                    continue
                if previous.get("status") == "failed" and not args.retry_failed:
                    print(f"[{position}/{total}] skip failed {key}", flush=True)
                    continue
                if new_runs >= args.max_new_runs:
                    print("budget cap reached; stopping before another online run", flush=True)
                    return
                new_runs += 1

                if mode == "branchlab":
                    script = ROOT / "branchlab" / "tau3_online_branch.py"
                    command = [
                        sys.executable,
                        str(script),
                        "--mode", "branchlab",
                        "--task-id", task,
                        "--branches", str(args.candidates),
                        "--prefix-reads", "0",
                        "--execution", "parallel",
                    ]
                else:
                    script = ROOT / "branchlab" / "tau3_independent_parallel.py"
                    command = [
                        sys.executable,
                        str(script),
                        "--mode", mode,
                        "--task-id", task,
                        "--runs", str(args.candidates),
                    ]
                command.extend(
                    [
                        "--seed", str(seed),
                        "--temperature", str(args.temperature),
                        "--model", args.model,
                    ]
                )
                log_path = LOGS / f"task{task}_seed{seed}_{mode}.log"
                checkpoint["runs"][key] = {
                    "status": "running",
                    "log": str(log_path),
                    "result": str(result_path),
                }
                save_checkpoint(checkpoint)
                print(f"[{position}/{total}] start {key}", flush=True)
                started = time.perf_counter()
                with log_path.open("w", encoding="utf-8") as log:
                    completed = subprocess.run(
                        command,
                        cwd=ROOT / "external" / "tau2-bench",
                        env=os.environ.copy(),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                elapsed = time.perf_counter() - started
                success = completed.returncode == 0 and valid_result(result_path)
                log_text = log_path.read_text(encoding="utf-8", errors="replace")
                insufficient_balance = "Insufficient Balance" in log_text
                checkpoint["runs"][key] = {
                    "status": "complete" if success else "failed",
                    "returncode": completed.returncode,
                    "elapsed_s": elapsed,
                    "log": str(log_path),
                    "result": str(result_path),
                }
                if insufficient_balance:
                    checkpoint["runs"][key]["failure_reason"] = (
                        "deepseek_insufficient_balance"
                    )
                save_checkpoint(checkpoint)
                print(
                    f"[{position}/{total}] {'done' if success else 'FAILED'} {key} {elapsed:.1f}s",
                    flush=True,
                )
                if insufficient_balance:
                    print(
                        "stopping matrix: DeepSeek reported insufficient balance",
                        flush=True,
                    )
                    return


if __name__ == "__main__":
    main()
