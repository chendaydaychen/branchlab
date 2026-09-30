"""Create a compact report for one completed TPC-C-derived parameter point."""
from __future__ import annotations

import argparse, json, statistics
from pathlib import Path
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]

def load(mode, workers, candidates, hot, seeds):
    rows=[]
    for seed in range(1,seeds+1):
        p=ROOT/"results"/f"tpcc_{mode}_w{workers}_c{candidates}_h{hot}_s{seed}.json"
        if not p.exists(): raise FileNotFoundError(p)
        rows.append(json.loads(p.read_text()))
    return rows

def main():
    p=argparse.ArgumentParser(); p.add_argument("--workers",type=int,required=True); p.add_argument("--candidates",type=int,required=True); p.add_argument("--hot-items",type=int,required=True); p.add_argument("--seeds",type=int,default=5); a=p.parse_args()
    groups={m:load(m,a.workers,a.candidates,a.hot_items,a.seeds) for m in ("2pl","occ","reuse")}
    summary=[]
    for m,rows in groups.items():
        summary.append((m,statistics.mean(r["throughput_ops_s"] for r in rows),statistics.stdev(r["throughput_ops_s"] for r in rows),statistics.mean(r["aborts"] for r in rows),sum(r["failed"] for r in rows),statistics.mean(r["discovery_executions"] for r in rows)))
    out=ROOT/"results"/f"tpcc_report_w{a.workers}_c{a.candidates}_h{a.hot_items}.md"
    lines=["# TPC-C-derived contention point", "", f"workers={a.workers}, candidates={a.candidates}, hot_items={a.hot_items}, seeds={a.seeds}", "", "| mode | throughput mean +/- sd | mean aborts | total failures | mean discovery executions |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {m} | {t:.2f} +/- {sd:.2f} | {ab:.1f} | {fail} | {d:.1f} |" for m,t,sd,ab,fail,d in summary]
    out.write_text("\n".join(lines)+"\n")
    names=[x[0] for x in summary]; colors=["#d95f02","#7570b3","#1b9e77"]
    fig,ax=plt.subplots(1,2,figsize=(9,3.8)); ax[0].bar(names,[x[1] for x in summary],yerr=[x[2] for x in summary],color=colors,capsize=5); ax[0].set(ylabel="Throughput (ops/s)",title="Mean +/- sample SD"); ax[1].bar(names,[x[3] for x in summary],color=colors); ax[1].set(ylabel="Mean aborts per run",title="Optimistic conflict cost")
    fig.suptitle(f"TPC-C-derived: {a.workers} workers, {a.candidates} candidates, {a.hot_items} hot item")
    fig.tight_layout(); image=ROOT/"figures"/f"tpcc_report_w{a.workers}_c{a.candidates}_h{a.hot_items}.png"; image.parent.mkdir(exist_ok=True); fig.savefig(image,dpi=180)
    print(out); print(image)
if __name__=="__main__": main()
