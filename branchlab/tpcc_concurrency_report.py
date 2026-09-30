"""Aggregate the completed 4/8/16-worker TPC-C-derived contention curve."""
from __future__ import annotations
import json, statistics
from pathlib import Path
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]; workers=(4,8,16); modes=("2pl","occ","reuse")
rows={}
for mode in modes:
    rows[mode]=[]
    for w in workers:
        samples=[json.loads((ROOT/"results"/f"tpcc_{mode}_w{w}_c4_h1_s{seed}.json").read_text()) for seed in range(1,6)]
        rows[mode].append((statistics.mean(x["throughput_ops_s"] for x in samples),statistics.stdev(x["throughput_ops_s"] for x in samples),statistics.mean(x["aborts"] for x in samples),sum(x["failed"] for x in samples)))
out=ROOT/"results"/"tpcc_concurrency_w4_w8_w16.md"
lines=["# TPC-C-derived high-contention concurrency sweep", "", "candidates=4, hot_items=1, tasks=40, discovery_ms=20, think_ms=30, seeds=5", "", "| workers | mode | throughput mean +/- sd | mean aborts | total failures |", "|---:|---|---:|---:|---:|"]
for i,w in enumerate(workers):
    for m in modes:
        t,sd,a,f=rows[m][i]; lines.append(f"| {w} | {m} | {t:.2f} +/- {sd:.2f} | {a:.1f} | {f} |")
out.write_text("\n".join(lines)+"\n")
colors={"2pl":"#d95f02","occ":"#7570b3","reuse":"#1b9e77"}; labels={"2pl":"2PL","occ":"OCC","reuse":"Reuse-OCC"}
fig,ax=plt.subplots(1,2,figsize=(10,4))
for m in modes:
    ax[0].errorbar(workers,[x[0] for x in rows[m]],yerr=[x[1] for x in rows[m]],marker="o",capsize=4,label=labels[m],color=colors[m])
    ax[1].plot(workers,[x[2] for x in rows[m]],marker="o",label=labels[m],color=colors[m])
ax[0].set(xlabel="Workers",ylabel="Throughput (ops/s)",title="Throughput mean +/- sample SD"); ax[1].set(xlabel="Workers",ylabel="Mean aborts per run",title="Conflict cost")
for a in ax: a.set_xticks(workers); a.grid(alpha=.25); a.legend()
fig.suptitle("TPC-C-derived New-Order: 4 candidates, 1 hot item, 5 seeds"); fig.tight_layout(); png=ROOT/"figures"/"tpcc_concurrency_w4_w8_w16.png"; png.parent.mkdir(exist_ok=True); fig.savefig(png,dpi=180)
print(out); print(png)
