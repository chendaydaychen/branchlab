"""Aggregate the five-seed TATP ablation."""
from __future__ import annotations
import json, math, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MODES = ("2pl", "occ", "reuse_strict", "semantic_occ", "semantic_reuse")
lines = ["# TATP-derived five-seed ablation: single-subscriber hotspot", "", "Configuration: PostgreSQL 16; 8 workers; 20 tasks × 4 candidates; one hot subscriber; 20 ms discovery; 10 ms decision; seeds 1–5. This is a TATP-derived experiment, not an official BenchBase score.", "", "| controller | throughput ops/s, mean ± 95% CI | commits / 80 | retries | common reads |", "|---|---:|---:|---:|---:|"]
for mode in MODES:
    data=[json.loads((ROOT/"results"/f"tatp_{mode}_w8_c4_h1_s{seed}.json").read_text()) for seed in range(1,6)]
    def stat(key):
        x=[r[key] for r in data]
        return statistics.mean(x),2.776*statistics.stdev(x)/math.sqrt(5)
    t,ci=stat("throughput_ops_s"); commits,_=stat("committed"); aborts,_=stat("aborts"); reads,_=stat("discovery_executions")
    lines.append(f"| {mode} | {t:.2f} ± {ci:.2f} | {commits:.1f} | {aborts:.1f} | {reads:.1f} |")
out=ROOT/"results"/"tatp_five_seed_ablation.md"
out.write_text("\n".join(lines)+"\n")
print("\n".join(lines))
