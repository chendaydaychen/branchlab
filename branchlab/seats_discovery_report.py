"""Aggregate and plot the five-seed common-prefix cost sweep."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
MODES = ("2pl", "occ", "reuse_strict", "semantic_occ", "semantic_reuse")
COSTS = (0, 5, 20, 100, 500)
LABELS = {
    "2pl": "2PL",
    "occ": "OCC",
    "reuse_strict": "Reuse-OCC",
    "semantic_occ": "Semantic-OCC",
    "semantic_reuse": "Semantic-Reuse-OCC",
}


def result_path(cost: int, mode: str, seed: int) -> Path:
    if cost == 20:
        # This is the identical c=4 point already collected in the candidate sweep.
        suffix = "candidate_scale"
    else:
        suffix = f"discovery_{cost}ms"
    return ROOT / "results" / f"seats_{mode}_w8_c4_h40_s{seed}_{suffix}.json"


def ci95(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), 2.776 * statistics.stdev(values) / math.sqrt(5)


records: dict[tuple[int, str], dict[str, object]] = {}
lines = [
    "# SEATS shared-prefix cost scaling (five seeds)",
    "",
    "Configuration: PostgreSQL 16, 8 workers, 40 tasks, 4 candidates/task, "
    "40 hot flights, 10 ms decision, winner-only materialization. The 20 ms "
    "point reuses the identical c=4 candidate-scaling runs. Values are mean ± 95% CI.",
    "",
    "The primary metric is end-to-end throughput. Per-operation latency is not used "
    "here because reused prefix work is accounted at task level rather than inside "
    "each branch transaction's latency timer.",
    "",
    "| prefix cost ms | controller | throughput ops/s | prefix executions | reuse hits | invariant violations |",
    "|---:|---|---:|---:|---:|---:|",
]

for cost in COSTS:
    for mode in MODES:
        data = [json.loads(result_path(cost, mode, seed).read_text()) for seed in range(1, 6)]
        throughput = ci95([row["throughput_ops_s"] for row in data])
        executions = statistics.mean(row["discovery_executions"] for row in data)
        hits = statistics.mean(row["discovery_reuse_hits"] for row in data)
        violations = sum(row["invariant_violations"] for row in data)
        records[cost, mode] = {
            "throughput": throughput,
            "executions": executions,
            "hits": hits,
        }
        lines.append(
            f"| {cost} | {mode} | {throughput[0]:.2f} ± {throughput[1]:.2f} | "
            f"{executions:.1f} | {hits:.1f} | {violations} |"
        )

lines.extend(["", "## Mechanism effect", ""])
for cost in COSTS:
    base = records[cost, "semantic_occ"]["throughput"][0]
    reuse = records[cost, "semantic_reuse"]["throughput"][0]
    lines.append(
        f"- {cost} ms: Semantic-Reuse-OCC is {reuse / base:.2f}× the throughput "
        f"of Semantic-OCC ({reuse:.2f} vs {base:.2f} ops/s)."
    )

report = ROOT / "results" / "seats_discovery_scale_five_seed.md"
report.write_text("\n".join(lines) + "\n")

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
positions = list(range(len(COSTS)))
for mode in MODES:
    ys = [records[cost, mode]["throughput"][0] for cost in COSTS]
    errors = [records[cost, mode]["throughput"][1] for cost in COSTS]
    axes[0].errorbar(positions, ys, yerr=errors, marker="o", capsize=3, label=LABELS[mode])

speedups = [
    records[cost, "semantic_reuse"]["throughput"][0]
    / records[cost, "semantic_occ"]["throughput"][0]
    for cost in COSTS
]
axes[1].plot(positions, speedups, marker="o", color="#d62728", linewidth=2)
axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1)
axes[0].set(
    xlabel="Shared-prefix cost (ms)",
    ylabel="End-to-end throughput (ops/s)",
    xticks=positions,
    xticklabels=COSTS,
)
axes[1].set(
    xlabel="Shared-prefix cost (ms)",
    ylabel="Semantic-Reuse / Semantic-OCC",
    xticks=positions,
    xticklabels=COSTS,
)
axes[0].grid(alpha=0.25)
axes[1].grid(alpha=0.25)
axes[0].legend(fontsize=8)
fig.tight_layout()
figure = ROOT / "figures" / "seats_discovery_scale_five_seed.png"
figure.parent.mkdir(exist_ok=True)
fig.savefig(figure, dpi=180)
plt.close(fig)

print("\n".join(lines))
print(figure)
