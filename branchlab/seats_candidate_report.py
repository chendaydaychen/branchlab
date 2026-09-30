"""Aggregate and plot the five-seed candidate-count scaling experiment."""
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
MODES=("2pl","occ","reuse_strict","semantic_occ","semantic_reuse")
CANDIDATES=(1,2,4,8)
LABELS={"2pl":"2PL","occ":"OCC","reuse_strict":"Reuse-OCC","semantic_occ":"Semantic-OCC","semantic_reuse":"Semantic-Reuse-OCC"}
records={}
lines=["# SEATS candidate-count scaling (five seeds)","",
       "Configuration: PostgreSQL 16, 8 workers, 40 tasks, 40 hot flights, 20 ms discovery, 10 ms decision, winner-only materialization. Values are mean ± 95% CI.","",
       "| candidates | controller | throughput ops/s | P99 ms | common reads | reuse hits | invariant violations |",
       "|---:|---|---:|---:|---:|---:|---:|"]
for candidate in CANDIDATES:
    for mode in MODES:
        data=[json.loads((ROOT/"results"/f"seats_{mode}_w8_c{candidate}_h40_s{seed}_candidate_scale.json").read_text()) for seed in range(1,6)]
        def stat(values):
            return statistics.mean(values),2.776*statistics.stdev(values)/math.sqrt(5)
        throughput=stat([x["throughput_ops_s"] for x in data])
        p99=stat([x["latency_ms"]["p99"] for x in data])
        reads=statistics.mean(x["discovery_executions"] for x in data)
        hits=statistics.mean(x["discovery_reuse_hits"] for x in data)
        violations=sum(x["invariant_violations"] for x in data)
        records[candidate,mode]=(throughput,p99,reads,hits)
        lines.append(f"| {candidate} | {mode} | {throughput[0]:.2f} ± {throughput[1]:.2f} | {p99[0]:.2f} ± {p99[1]:.2f} | {reads:.1f} | {hits:.1f} | {violations} |")
out=ROOT/"results"/"seats_candidate_scale_five_seed.md"; out.write_text("\n".join(lines)+"\n")
fig,axes=plt.subplots(1,2,figsize=(11,4))
for mode in MODES:
    ys=[records[c,mode][0][0] for c in CANDIDATES]; es=[records[c,mode][0][1] for c in CANDIDATES]
    axes[0].errorbar(CANDIDATES,ys,yerr=es,marker="o",capsize=3,label=LABELS[mode])
    axes[1].plot(CANDIDATES,[records[c,mode][2] for c in CANDIDATES],marker="o",label=LABELS[mode])
axes[0].set(xlabel="Candidates per task",ylabel="Throughput (ops/s)",xticks=CANDIDATES)
axes[1].set(xlabel="Candidates per task",ylabel="Common-prefix executions",xticks=CANDIDATES)
axes[0].grid(alpha=.25); axes[1].grid(alpha=.25); axes[0].legend(fontsize=8)
fig.tight_layout(); figure=ROOT/"figures"/"seats_candidate_scale_five_seed.png"; figure.parent.mkdir(exist_ok=True); fig.savefig(figure,dpi=180); plt.close(fig)
print("\n".join(lines)); print(figure)
