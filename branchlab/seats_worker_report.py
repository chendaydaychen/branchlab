"""Aggregate and plot the five-seed SEATS worker-scaling experiment."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
MODES = ("2pl", "occ", "reuse_strict", "semantic_occ", "semantic_reuse")
WORKERS = (1, 4, 8, 16, 32)
HOTSPOTS = (1, 40)
LABELS = {
    "2pl": "2PL",
    "occ": "OCC",
    "reuse_strict": "Reuse-OCC",
    "semantic_occ": "Semantic-OCC",
    "semantic_reuse": "Semantic-Reuse-OCC",
}


def ci95(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), 2.776 * statistics.stdev(values) / math.sqrt(5)


records: dict[tuple[int, int, str], dict[str, object]] = {}
lines = [
    "# SEATS worker scaling (five seeds)",
    "",
    "Configuration: PostgreSQL 16, 40 tasks, 4 candidates/task, 20 ms discovery, "
    "10 ms decision, winner-only materialization. Hotspot h=1 is the high-conflict "
    "case and h=40 is the low-conflict control. Values are mean ± 95% CI.",
    "",
    "Goodput counts only successful branch commits. It is derived as completion "
    "throughput × committed / operations, so exhausted retries are not credited as useful work.",
    "",
    "| h | workers | controller | goodput ops/s | success % | P99 ms | retries | invariant violations |",
    "|---:|---:|---|---:|---:|---:|---:|---:|",
]

for hotspot in HOTSPOTS:
    for workers in WORKERS:
        for mode in MODES:
            data = [
                json.loads(
                    (
                        ROOT
                        / "results"
                        / f"seats_{mode}_w{workers}_c4_h{hotspot}_s{seed}_worker_scale.json"
                    ).read_text()
                )
                for seed in range(1, 6)
            ]
            goodput_values = [
                row["throughput_ops_s"] * row["committed"] / row["operations"] for row in data
            ]
            goodput = ci95(goodput_values)
            success = ci95([100 * row["committed"] / row["operations"] for row in data])
            p99 = ci95([row["latency_ms"]["p99"] for row in data])
            retries = ci95([row["aborts"] for row in data])
            violations = sum(row["invariant_violations"] for row in data)
            records[hotspot, workers, mode] = {
                "goodput": goodput,
                "success": success,
                "p99": p99,
                "retries": retries,
            }
            lines.append(
                f"| {hotspot} | {workers} | {mode} | {goodput[0]:.2f} ± {goodput[1]:.2f} | "
                f"{success[0]:.2f} ± {success[1]:.2f} | {p99[0]:.2f} ± {p99[1]:.2f} | "
                f"{retries[0]:.1f} ± {retries[1]:.1f} | {violations} |"
            )

lines.extend(["", "## Key comparisons", ""])
for hotspot in HOTSPOTS:
    complete = records[hotspot, 32, "semantic_reuse"]["goodput"][0]
    occ = records[hotspot, 32, "occ"]["goodput"][0]
    two_pl = records[hotspot, 32, "2pl"]["goodput"][0]
    lines.append(
        f"- h={hotspot}, 32 workers: Semantic-Reuse-OCC goodput is {complete / occ:.2f}× OCC "
        f"and {complete / two_pl:.2f}× 2PL ({complete:.2f} vs {occ:.2f} vs {two_pl:.2f} ops/s)."
    )

report = ROOT / "results" / "seats_worker_scale_five_seed.md"
report.write_text("\n".join(lines) + "\n")

fig, axes = plt.subplots(2, 2, figsize=(12, 8))
for mode in MODES:
    for hotspot, axis in ((1, axes[0, 0]), (40, axes[0, 1])):
        ys = [records[hotspot, workers, mode]["goodput"][0] for workers in WORKERS]
        errors = [records[hotspot, workers, mode]["goodput"][1] for workers in WORKERS]
        axis.errorbar(WORKERS, ys, yerr=errors, marker="o", capsize=3, label=LABELS[mode])
    axes[1, 0].plot(
        WORKERS,
        [records[1, workers, mode]["success"][0] for workers in WORKERS],
        marker="o",
        label=LABELS[mode],
    )
    axes[1, 1].plot(
        WORKERS,
        [records[1, workers, mode]["p99"][0] for workers in WORKERS],
        marker="o",
        label=LABELS[mode],
    )

axes[0, 0].set_title("High conflict (h=1)")
axes[0, 1].set_title("Low conflict (h=40)")
axes[0, 0].set_ylabel("Goodput (successful ops/s)")
axes[0, 1].set_ylabel("Goodput (successful ops/s)")
axes[1, 0].set_ylabel("Success rate (%)")
axes[1, 1].set_ylabel("P99 latency (ms)")
for axis in axes.flat:
    axis.set_xlabel("Workers")
    axis.set_xticks(WORKERS)
    axis.grid(alpha=0.25)
axes[1, 0].set_ylim(80, 101)
axes[0, 0].legend(fontsize=8)
fig.tight_layout()
figure = ROOT / "figures" / "seats_worker_scale_five_seed.png"
figure.parent.mkdir(exist_ok=True)
fig.savefig(figure, dpi=180)
plt.close(fig)

print("\n".join(lines))
print(figure)
