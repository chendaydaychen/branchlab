"""Paired TPC-C-derived parameter sweep and plotting."""
from __future__ import annotations

import argparse, csv, json, subprocess, sys
from pathlib import Path
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]; RESULTS=ROOT/"results"; FIGURES=ROOT/"figures"

def call(parts):
    done=subprocess.run([sys.executable,"-m","branchlab.tpcc_runner",*parts],cwd=ROOT,text=True,capture_output=True,check=True)
    return None if parts[0]=="setup" else json.loads(done.stdout.split("\nraw result:")[0])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seeds",type=int,default=2); p.add_argument("--candidates",nargs="+",type=int,default=[1,2,4,8]); p.add_argument("--hot-items",nargs="+",type=int,default=[1,2,8]); p.add_argument("--workers",type=int,default=4); p.add_argument("--tasks",type=int,default=30); p.add_argument("--discovery-ms",type=int,default=20); p.add_argument("--think-ms",type=int,default=5)
    a=p.parse_args(); rows=[]
    common=["--warehouses","4","--districts","4","--customers","50","--items","100"]
    for hot in a.hot_items:
      for candidates in a.candidates:
       for seed in range(1,a.seeds+1):
        for mode in ("2pl","occ","reuse"):
         call(["setup",*common])
         row=call(["run",*common,"--mode",mode,"--workers",str(a.workers),"--tasks",str(a.tasks),"--candidates",str(candidates),"--hot-items",str(hot),"--discovery-ms",str(a.discovery_ms),"--think-ms",str(a.think_ms),"--seed",str(seed)])
         rows.append(row); print(f"done hot={hot} candidates={candidates} seed={seed} mode={mode}")
    RESULTS.mkdir(exist_ok=True); path=RESULTS/"tpcc_candidate_hotspot_sweep.csv"; fields=sorted({k for r in rows for k,v in r.items() if not isinstance(v,dict)})
    with path.open("w",newline="") as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows([{k:r.get(k) for k in fields} for r in rows])
    FIGURES.mkdir(exist_ok=True); fig,axes=plt.subplots(1,len(a.hot_items),figsize=(5*len(a.hot_items),4),sharey=True)
    if len(a.hot_items)==1: axes=[axes]
    for ax,hot in zip(axes,a.hot_items):
      for mode,label,color in (("2pl","2PL","#d95f02"),("occ","OCC","#7570b3"),("reuse","Reuse-OCC","#1b9e77")):
       ys=[]
       for c in a.candidates:
        group=[r for r in rows if r["hot_items"]==hot and r["candidates_per_task"]==c and r["mode"]==mode]; ys.append(sum(r["throughput_ops_s"] for r in group)/len(group))
       ax.plot(a.candidates,ys,"o-",label=label,color=color)
      ax.set(title=f"Hot items = {hot}",xlabel="Candidates per task"); ax.set_xticks(a.candidates); ax.grid(alpha=.25)
    axes[0].set_ylabel("Mean throughput (ops/s)"); axes[-1].legend(); fig.suptitle(f"TPC-C-derived New-Order ({a.seeds} seeds, {a.workers} workers)"); fig.tight_layout()
    out=FIGURES/"tpcc_candidate_hotspot_sweep.png"; fig.savefig(out,dpi=180); print(f"summary: {path}\nfigure: {out}")
if __name__=="__main__": main()
