"""Run paired three-way experiments and create group-meeting figures."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


def invoke(args: list[str]) -> dict | None:
    completed = subprocess.run([sys.executable, "-m", "branchlab.runner", *args], cwd=ROOT, check=True, text=True, capture_output=True)
    if args == ["setup"]:
        return None
    # The runner prints JSON followed by a path line.
    return json.loads(completed.stdout.split("\nraw result:")[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--candidates", nargs="+", type=int, default=[1, 2, 4, 8])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tasks", type=int, default=40)
    parser.add_argument("--hot-flights", type=int, default=2)
    parser.add_argument("--discovery-ms", type=int, default=30)
    parser.add_argument("--think-ms", type=int, default=5)
    args = parser.parse_args()

    rows = []
    for candidates in args.candidates:
        for seed in range(1, args.seeds + 1):
            for mode in ("2pl", "occ", "reuse"):
                invoke(["setup"])
                row = invoke([
                    "run", "--mode", mode, "--workers", str(args.workers),
                    "--candidates", str(candidates), "--tasks", str(args.tasks),
                    "--hot-flights", str(args.hot_flights), "--discovery-ms", str(args.discovery_ms),
                    "--think-ms", str(args.think_ms), "--seed", str(seed),
                ])
                rows.append(row)
                print(f"completed mode={mode} candidates={candidates} seed={seed}")

    RESULTS.mkdir(exist_ok=True)
    csv_path = RESULTS / "travel_candidate_sweep.csv"
    fields = sorted({key for row in rows for key, value in row.items() if not isinstance(value, dict)})
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{k: v for k, v in row.items() if k in fields} for row in rows])

    FIGURES.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for mode, label, color in (("2pl", "2PL", "#d95f02"), ("occ", "OCC", "#7570b3"), ("reuse", "Reuse-OCC", "#1b9e77")):
        xs, tputs, aborts = [], [], []
        for candidates in args.candidates:
            group = [r for r in rows if r["mode"] == mode and r["candidates_per_task"] == candidates]
            xs.append(candidates)
            tputs.append(sum(r["throughput_ops_s"] for r in group) / len(group))
            aborts.append(sum(r["retry_rate"] for r in group) / len(group))
        axes[0].plot(xs, tputs, marker="o", label=label, color=color)
        axes[1].plot(xs, aborts, marker="o", label=label, color=color)
    axes[0].set(xlabel="Candidates per task", ylabel="Throughput (ops/s)", title="Candidate scaling")
    axes[1].set(xlabel="Candidates per task", ylabel="Aborts per operation", title="Conflict cost")
    for ax in axes:
        ax.set_xticks(args.candidates)
        ax.grid(alpha=0.25)
        ax.legend()
    fig.suptitle(f"Travel microbenchmark: {args.seeds} seeds, {args.workers} workers, {args.hot_flights} hot flights")
    fig.tight_layout()
    figure_path = FIGURES / "travel_candidate_sweep.png"
    fig.savefig(figure_path, dpi=180)
    print(f"summary: {csv_path}\nfigure: {figure_path}")


if __name__ == "__main__":
    main()
