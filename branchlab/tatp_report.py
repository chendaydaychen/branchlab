"""Aggregate reproducible TATP-derived run JSON into a candid Markdown report."""
from __future__ import annotations
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = sorted(ROOT.glob("results/tatp_*_w8_c4_h1_s[123].json"))
groups = {}
for path in files:
    row = json.loads(path.read_text())
    groups.setdefault(row["mode"], []).append(row)

def mean(key, mode):
    return statistics.mean(row[key] for row in groups[mode])
def sd(key, mode):
    values = [row[key] for row in groups[mode]]
    return statistics.stdev(values) if len(values) > 1 else 0.0

lines = [
    "# TATP-derived single-hotspot result",
    "",
    "This is a BranchLab TATP-derived experiment, **not** an official BenchBase/TATP result.",
    "TATP entity/transaction semantics follow the public BenchBase implementation; row versions and",
    "the branch audit table are experimental extensions. All runs: PostgreSQL 16, 8 workers,",
    "30 tasks × 4 candidate branches, one hot subscriber, 20 ms discovery, 10 ms decision,",
    "12 OCC retries, seeds 1–3.",
    "",
    "| mode | throughput ops/s (mean ± sd) | commits / 120 | failures / 120 | aborts | common reads | lock wait |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for mode in ("2pl", "occ", "reuse"):
    lines.append(
        f"| {mode} | {mean('throughput_ops_s', mode):.2f} ± {sd('throughput_ops_s', mode):.2f} | "
        f"{mean('committed', mode):.1f} | {mean('failed', mode):.1f} | {mean('aborts', mode):.1f} | "
        f"{mean('discovery_executions', mode):.1f} | {mean('lock_wait_ms_total', mode):.0f} ms |"
    )
lines += [
    "",
    "## Interpretation",
    "",
    "- 2PL is the only mode with all 120 commits, but it holds the subscriber row lock across",
    "  discovery and decision, producing roughly 29 s aggregate wait per run.",
    "- OCC has slightly higher attempted-operation throughput, but the single writer hotspot creates",
    "  hundreds of validation retries and about 37 exhausted branches.",
    "- Reuse performs exactly one common read per task (30 rather than 120), with 90 sibling cache",
    "  hits. It does **not** win throughput on this deliberately adversarial write hotspot: the shared",
    "  snapshot is often stale before a sibling can commit, so validation correctly causes retries.",
    "- Thus these runs support the safety and compute-elimination claims, but do not yet support an",
    "  unconditional end-to-end speedup claim. A mixed read/private-write TATP scenario and SEATS",
    "  should be added before making a broader performance claim.",
    "",
    "Raw JSON files are stored in the results directory with tatp prefixes.",
]
out = ROOT / "results" / "tatp_single_hotspot_report.md"
out.write_text("\n".join(lines) + "\n")
print(out)
print("\n".join(lines))
