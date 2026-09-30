"""Aggregate the 32-worker, 120-task SEATS confirmation runs."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
MODES = ("2pl", "occ", "semantic_reuse")
HOTSPOTS = (1, 40)
LABELS = {"2pl": "2PL", "occ": "OCC", "semantic_reuse": "Semantic-Reuse-OCC"}


def ci95(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), 2.776 * statistics.stdev(values) / math.sqrt(5)


records: dict[tuple[int, str], dict[str, tuple[float, float] | int]] = {}
lines = [
    "# SEATS 32-worker long-run confirmation (five seeds)",
    "",
    "Configuration: PostgreSQL 16, 32 workers, 120 tasks, 4 candidates/task "
    "(480 branch operations/run), 20 ms discovery, 10 ms decision, winner-only "
    "materialization. Values are mean ± 95% CI.",
    "",
    "| h | controller | goodput ops/s | success % | P99 ms | retries | prefix executions | invariant violations |",
    "|---:|---|---:|---:|---:|---:|---:|---:|",
]

for hotspot in HOTSPOTS:
    for mode in MODES:
        data = [
            json.loads(
                (
                    ROOT
                    / "results"
                    / f"seats_{mode}_w32_c4_h{hotspot}_s{seed}_long_stress.json"
                ).read_text()
            )
            for seed in range(1, 6)
        ]
        goodput = ci95(
            [row["throughput_ops_s"] * row["committed"] / row["operations"] for row in data]
        )
        success = ci95([100 * row["committed"] / row["operations"] for row in data])
        p99 = ci95([row["latency_ms"]["p99"] for row in data])
        retries = ci95([row["aborts"] for row in data])
        prefix = ci95([row["discovery_executions"] for row in data])
        violations = sum(row["invariant_violations"] for row in data)
        records[hotspot, mode] = {
            "goodput": goodput,
            "success": success,
            "p99": p99,
            "retries": retries,
            "prefix": prefix,
            "violations": violations,
        }
        lines.append(
            f"| {hotspot} | {mode} | {goodput[0]:.2f} ± {goodput[1]:.2f} | "
            f"{success[0]:.2f} ± {success[1]:.2f} | {p99[0]:.2f} ± {p99[1]:.2f} | "
            f"{retries[0]:.1f} ± {retries[1]:.1f} | {prefix[0]:.1f} | {violations} |"
        )

lines.extend(["", "## Main effects", ""])
for hotspot in HOTSPOTS:
    ours = records[hotspot, "semantic_reuse"]["goodput"][0]
    occ = records[hotspot, "occ"]["goodput"][0]
    two_pl = records[hotspot, "2pl"]["goodput"][0]
    lines.append(
        f"- h={hotspot}: complete design is {ours / occ:.2f}× OCC and {ours / two_pl:.2f}× 2PL "
        f"in successful goodput ({ours:.2f} vs {occ:.2f} vs {two_pl:.2f} ops/s)."
    )

report = ROOT / "results" / "seats_long_stress_five_seed.md"
report.write_text("\n".join(lines) + "\n")

fig, axes = plt.subplots(1, 3, figsize=(12, 4))
x = list(range(len(MODES)))
colors = ("#1f77b4", "#ff7f0e", "#9467bd")
for index, hotspot in enumerate(HOTSPOTS):
    offset = -0.18 if hotspot == 1 else 0.18
    axes[0].bar(
        [position + offset for position in x],
        [records[hotspot, mode]["goodput"][0] for mode in MODES],
        width=0.36,
        yerr=[records[hotspot, mode]["goodput"][1] for mode in MODES],
        capsize=3,
        label=f"h={hotspot}",
        alpha=0.85,
    )
axes[1].bar(
    x,
    [records[1, mode]["success"][0] for mode in MODES],
    color=colors,
)
axes[2].bar(
    x,
    [records[1, mode]["p99"][0] for mode in MODES],
    color=colors,
    yerr=[records[1, mode]["p99"][1] for mode in MODES],
    capsize=3,
)
axes[0].set_ylabel("Goodput (successful ops/s)")
axes[1].set_ylabel("High-conflict success rate (%)")
axes[2].set_ylabel("High-conflict P99 latency (ms)")
axes[1].set_ylim(75, 101)
for axis in axes:
    axis.set_xticks(x, [LABELS[mode] for mode in MODES], rotation=15, ha="right")
    axis.grid(axis="y", alpha=0.25)
axes[0].legend()
fig.tight_layout()
figure = ROOT / "figures" / "seats_long_stress_five_seed.png"
figure.parent.mkdir(exist_ok=True)
fig.savefig(figure, dpi=180)
plt.close(fig)

print("\n".join(lines))
print(figure)
