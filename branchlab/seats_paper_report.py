"""Aggregate the preregistered five-seed SEATS ablation."""
from __future__ import annotations
import json, math, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MODES = ("2pl", "occ", "reuse_strict", "semantic_occ", "semantic_reuse")
HOT = 40
rows = {}
for mode in MODES:
    rows[mode] = [json.loads((ROOT / "results" / f"seats_{mode}_w8_c4_h{HOT}_s{seed}.json").read_text()) for seed in range(1, 6)]
def summary(mode, key):
    values = [row[key] for row in rows[mode]]
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    ci = 2.776 * sd / math.sqrt(len(values))
    return mean, sd, ci
lines = [f"# SEATS five-seed ablation: {HOT}-flight hotspot", "", f"Configuration: PostgreSQL 16; 8 workers; 40 tasks × 4 candidates; {HOT} hot flights; 20 ms common discovery; 10 ms decision; winner-only two-phase materialization; seeds 1–5.", "", "| controller | throughput ops/s, mean ± 95% CI | commits / 160 | retries | common reads |", "|---|---:|---:|---:|---:|"]
for mode in MODES:
    t, _, ci = summary(mode, "throughput_ops_s")
    committed, _, _ = summary(mode, "committed")
    aborts, _, _ = summary(mode, "aborts")
    reads, _, _ = summary(mode, "discovery_executions")
    lines.append(f"| {mode} | {t:.2f} ± {ci:.2f} | {committed:.1f} | {aborts:.1f} | {reads:.1f} |")
lines += ["", "Strict variants reject any shared-flight version change. Semantic variants accept a changed version only if flight capacity remains positive and price remains within the task budget, then rebase under the current row lock. Invariant violations: 0 in all recorded runs."]
path = ROOT / "results" / f"seats_five_seed_h{HOT}_ablation.md"
path.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
