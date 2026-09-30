"""Plot the measured three-way parallel performance pilot."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
data = json.loads(
    (ROOT / "results" / "tau3_parallel_performance_comparison.json").read_text(
        encoding="utf-8"
    )
)["rows"]

labels = ["2PL\nindependent", "Strict OCC\nindependent", "BranchLab"]
keys = ["2pl", "occ", "branchlab"]
colors = ["#8c8c8c", "#c47f3a", "#2c8c69"]
metrics = [
    ("wallclock_s", "Wall-clock time", "seconds", "{:.2f}"),
    ("cost_usd", "LLM cost", "USD", "${:.4f}"),
    ("physical_reads", "Database I/O", "physical reads", "{:.0f}"),
]

fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.2))
for axis, (metric, title, ylabel, value_format) in zip(axes, metrics):
    values = [data[key][metric] for key in keys]
    bars = axis.bar(labels, values, color=colors, width=0.68)
    axis.set_title(title, fontsize=12, weight="bold")
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.22)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)
    axis.set_ylim(0, max(values) * 1.24)
    for bar, value in zip(bars, values):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(values) * 0.035,
            value_format.format(value),
            ha="center",
            va="bottom",
            fontsize=10,
        )

fig.suptitle(
    "Tau3 Airline Task 11 — Three Parallel Candidates (all systems 3/3 correct)",
    fontsize=14,
    weight="bold",
)
fig.text(
    0.5,
    0.01,
    "DeepSeek Flash; one base seed pilot. Lower is better. BranchLab includes automatic fork-probe overhead.",
    ha="center",
    fontsize=9,
    color="#555555",
)
fig.tight_layout(rect=(0, 0.06, 1, 0.91))
output = ROOT / "figures" / "tau3_parallel_performance_comparison.png"
fig.savefig(output, dpi=220, bbox_inches="tight")
print(output)
