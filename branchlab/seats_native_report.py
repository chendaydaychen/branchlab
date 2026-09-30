"""Compare BranchLab with PostgreSQL native isolation baselines."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
MODES = ("2pl", "occ", "pg_rc", "pg_rr", "pg_ssi", "semantic_reuse")
WORKERS = (8, 32)
HOTSPOTS = (1, 40)
LABELS = {
    "2pl": "2PL",
    "occ": "OCC",
    "pg_rc": "PG-RC",
    "pg_rr": "PG-RR",
    "pg_ssi": "PG-SSI",
    "semantic_reuse": "BranchLab",
}


def ci95(values: list[float]) -> tuple[float, float]:
    return statistics.mean(values), 2.776 * statistics.stdev(values) / math.sqrt(5)


def path_for(mode: str, workers: int, hotspot: int, seed: int) -> Path:
    tag = "native_baseline" if mode.startswith("pg_") else "worker_scale"
    return ROOT / "results" / f"seats_{mode}_w{workers}_c4_h{hotspot}_s{seed}_{tag}.json"


records: dict[tuple[int, int, str], dict[str, tuple[float, float] | int]] = {}
lines = [
    "# PostgreSQL native-isolation baseline comparison (five seeds)",
    "",
    "Configuration: PostgreSQL 16, 40 tasks, 4 candidates/task, 20 ms discovery, "
    "10 ms decision, winner-only materialization. PG-RR and PG-SSI retry serialization "
    "failures with the same retry limit (12) as OCC. Values are mean ± 95% CI.",
    "",
    "PG-RC protects capacity with an atomic conditional update but does not revalidate "
    "task predicates such as the current price; its safety under semantic disturbances "
    "must therefore be read together with the differential-fuzz report.",
    "",
    "| h | workers | controller | goodput ops/s | success % | P99 ms | retries | violations |",
    "|---:|---:|---|---:|---:|---:|---:|---:|",
]

for hotspot in HOTSPOTS:
    for workers in WORKERS:
        for mode in MODES:
            data = [json.loads(path_for(mode, workers, hotspot, seed).read_text()) for seed in range(1, 6)]
            goodput = ci95(
                [
                    row.get("goodput_ops_s", row["throughput_ops_s"] * row["committed"] / row["operations"])
                    for row in data
                ]
            )
            success = ci95([100 * row["committed"] / row["operations"] for row in data])
            p99 = ci95([row["latency_ms"]["p99"] for row in data])
            retries = ci95([row["aborts"] for row in data])
            violations = sum(row["invariant_violations"] for row in data)
            records[hotspot, workers, mode] = {
                "goodput": goodput,
                "success": success,
                "p99": p99,
                "retries": retries,
                "violations": violations,
            }
            lines.append(
                f"| {hotspot} | {workers} | {LABELS[mode]} | {goodput[0]:.2f} ± {goodput[1]:.2f} | "
                f"{success[0]:.2f} ± {success[1]:.2f} | {p99[0]:.2f} ± {p99[1]:.2f} | "
                f"{retries[0]:.1f} ± {retries[1]:.1f} | {violations} |"
            )

report = ROOT / "results" / "seats_native_baselines_five_seed.md"
report.write_text("\n".join(lines) + "\n")

fig, axes = plt.subplots(2, 2, figsize=(13, 8))
positions = list(range(len(MODES)))
for row_index, hotspot in enumerate(HOTSPOTS):
    for column_index, workers in enumerate(WORKERS):
        axis = axes[row_index, column_index]
        values = [records[hotspot, workers, mode]["goodput"][0] for mode in MODES]
        errors = [records[hotspot, workers, mode]["goodput"][1] for mode in MODES]
        axis.bar(positions, values, yerr=errors, capsize=3)
        axis.set_title(f"h={hotspot}, workers={workers}")
        axis.set_ylabel("Goodput (successful ops/s)")
        axis.set_xticks(positions, [LABELS[mode] for mode in MODES], rotation=25, ha="right")
        axis.grid(axis="y", alpha=0.25)
fig.tight_layout()
figure = ROOT / "figures" / "seats_native_baselines_five_seed.png"
figure.parent.mkdir(exist_ok=True)
fig.savefig(figure, dpi=180)
plt.close(fig)

print("\n".join(lines))
print(figure)
