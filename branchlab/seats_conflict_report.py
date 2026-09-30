"""Build the three-level conflict-sweep table from complete five-seed runs."""
from __future__ import annotations
import json, math, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MODES = ("2pl", "occ", "reuse_strict", "semantic_occ", "semantic_reuse")
HOTS = (1, 16, 40)
lines = ["# SEATS five-seed conflict sweep", "", "All configurations use PostgreSQL 16, 8 workers, 40 tasks × 4 candidates, winner-only two-phase materialization, 20 ms shared discovery, and 10 ms decision. Mean ± 95% CI uses Student-t critical value 2.776 for n=5.", "", "| hot flights | controller | throughput ops/s, mean ± 95% CI | commits / 160 | retries | shared reads |", "|---:|---|---:|---:|---:|---:|"]
for hot in HOTS:
    for mode in MODES:
        data = [json.loads((ROOT / "results" / f"seats_{mode}_w8_c4_h{hot}_s{seed}.json").read_text()) for seed in range(1,6)]
        def metric(key):
            values = [row[key] for row in data]
            return statistics.mean(values), 2.776 * statistics.stdev(values) / math.sqrt(5)
        t, ci = metric("throughput_ops_s")
        commits, _ = metric("committed")
        aborts, _ = metric("aborts")
        reads, _ = metric("discovery_executions")
        lines.append(f"| {hot} | {mode} | {t:.2f} ± {ci:.2f} | {commits:.1f} | {aborts:.1f} | {reads:.1f} |")
out = ROOT / "results" / "seats_conflict_sweep_five_seed.md"
out.write_text("\n".join(lines)+"\n")
print("\n".join(lines))
