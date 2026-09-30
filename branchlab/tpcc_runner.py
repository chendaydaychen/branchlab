"""TPC-C-derived speculative New-Order benchmark (not an official TPC-C run)."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import statistics
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg


DSN = "postgresql://branchlab:branchlab@localhost:55432/branchlab"
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


@dataclass(frozen=True)
class Common:
    w: int; d: int; c: int; wv: int; dv: int; cv: int


@dataclass
class Outcome:
    ok: bool; aborts: int; latency_ms: float; lock_wait_ms: float = 0.0


def conn(): return psycopg.connect(DSN, autocommit=False)


def setup(args) -> None:
    with conn() as db:
        with db.cursor() as cur:
            cur.execute((ROOT / "tpcc_derived" / "schema.sql").read_text())
            cur.executemany("INSERT INTO tpcc_derived.warehouse(w_id,w_tax) VALUES(%s,%s)", [(w, .08) for w in range(1, args.warehouses + 1)])
            cur.executemany("INSERT INTO tpcc_derived.district(d_w_id,d_id,d_tax,d_next_o_id) VALUES(%s,%s,%s,%s)", [(w,d,.05,1) for w in range(1,args.warehouses+1) for d in range(1,args.districts+1)])
            cur.executemany("INSERT INTO tpcc_derived.customer(c_w_id,c_d_id,c_id,c_discount) VALUES(%s,%s,%s,%s)", [(w,d,c,.10) for w in range(1,args.warehouses+1) for d in range(1,args.districts+1) for c in range(1,args.customers+1)])
            cur.executemany("INSERT INTO tpcc_derived.item(i_id,i_price) VALUES(%s,%s)", [(i, 100+i) for i in range(1,args.items+1)])
            cur.executemany("INSERT INTO tpcc_derived.stock(s_w_id,s_i_id,s_quantity) VALUES(%s,%s,%s)", [(w,i,1000) for w in range(1,args.warehouses+1) for i in range(1,args.items+1)])
        db.commit()
    print(f"initialized TPC-C-derived: w={args.warehouses}, d={args.districts}, c={args.customers}, items={args.items}")


def common_read(cur, w, d, c, lock=False) -> Common:
    suffix = " FOR UPDATE OF w, d, c" if lock else ""
    cur.execute("SELECT w.row_version,d.row_version,c.row_version FROM tpcc_derived.warehouse w JOIN tpcc_derived.district d ON d.d_w_id=w.w_id JOIN tpcc_derived.customer c ON c.c_w_id=d.d_w_id AND c.c_d_id=d.d_id WHERE w.w_id=%s AND d.d_id=%s AND c.c_id=%s" + suffix, (w,d,c))
    row = cur.fetchone()
    if not row: raise RuntimeError("missing TPC-C-derived common state")
    return Common(w,d,c,*row)


def validate_common(cur, x: Common) -> bool:
    cur.execute("SELECT row_version FROM tpcc_derived.warehouse WHERE w_id=%s FOR UPDATE", (x.w,))
    if cur.fetchone()[0] != x.wv: return False
    cur.execute("SELECT row_version FROM tpcc_derived.district WHERE d_w_id=%s AND d_id=%s FOR UPDATE", (x.w,x.d))
    if cur.fetchone()[0] != x.dv: return False
    cur.execute("SELECT row_version FROM tpcc_derived.customer WHERE c_w_id=%s AND c_d_id=%s AND c_id=%s FOR UPDATE", (x.w,x.d,x.c))
    return cur.fetchone()[0] == x.cv


def job(task, candidate, args):
    w = (task % args.warehouses) + 1
    d = (task % args.districts) + 1
    c = (task % args.customers) + 1
    supplying = ((task + candidate) % args.warehouses) + 1
    item = ((task * 13 + candidate * 7) % args.hot_items) + 1
    return task, candidate, task * 100 + candidate, w, d, c, supplying, item


def commit(cur, x, branch, supplying, item, task, candidate, observed_stock_version=None) -> bool:
    if not validate_common(cur, x): return False
    cur.execute("SELECT s_quantity,row_version FROM tpcc_derived.stock WHERE s_w_id=%s AND s_i_id=%s FOR UPDATE", (supplying,item))
    stock = cur.fetchone()
    if not stock or stock[0] <= 0: return False
    if observed_stock_version is not None and stock[1] != observed_stock_version: return False
    cur.execute("UPDATE tpcc_derived.stock SET s_quantity=s_quantity-1,row_version=row_version+1 WHERE s_w_id=%s AND s_i_id=%s AND row_version=%s", (supplying,item,stock[1]))
    if cur.rowcount != 1: return False
    cur.execute("INSERT INTO tpcc_derived.candidate_order(branch_id,w_id,d_id,c_id,supplying_w_id,i_id,amount) VALUES(%s,%s,%s,%s,%s,%s,%s)", (branch,x.w,x.d,x.c,supplying,item,100+item))
    return True


def two_pl(j, args) -> Outcome:
    task,candidate,branch,w,d,c,supplying,item = j; started=time.perf_counter()
    with conn() as db:
        with db.cursor() as cur:
            ws=time.perf_counter(); x=common_read(cur,w,d,c,True)
            cur.execute("SELECT s_quantity FROM tpcc_derived.stock WHERE s_w_id=%s AND s_i_id=%s FOR UPDATE", (supplying,item)); cur.fetchone()
            wait=(time.perf_counter()-ws)*1000; time.sleep((args.discovery_ms+args.think_ms)/1000)
            ok=commit(cur,x,branch,supplying,item,task,candidate)
            (db.commit if ok else db.rollback)()
    return Outcome(ok,0 if ok else 1,(time.perf_counter()-started)*1000,wait)


def occ(j,args,cached=None) -> Outcome:
    task,candidate,branch,w,d,c,supplying,item = j; started=time.perf_counter(); aborts=0
    for attempt in range(12):
        with conn() as db:
            with db.cursor() as cur:
                x = cached if cached is not None and attempt == 0 else common_read(cur,w,d,c)
                if cached is None or attempt: time.sleep(args.discovery_ms/1000)
                cur.execute("SELECT s_quantity,row_version FROM tpcc_derived.stock WHERE s_w_id=%s AND s_i_id=%s", (supplying,item))
                stock = cur.fetchone()
                if not stock: db.rollback(); return Outcome(False,aborts,(time.perf_counter()-started)*1000)
                time.sleep(args.think_ms/1000); ok=commit(cur,x,branch,supplying,item,task,candidate,stock[1])
                if ok: db.commit(); return Outcome(True,aborts,(time.perf_counter()-started)*1000)
                db.rollback(); aborts+=1
    return Outcome(False,aborts,(time.perf_counter()-started)*1000)


class Cache:
    def __init__(self, ms): self.ms=ms; self.mu=threading.Lock(); self.data={}; self.misses=0; self.hits=0
    def get(self, task, w,d,c):
        with self.mu:
            old=self.data.get(task)
            if old is None: event=threading.Event(); self.data[task]=(event,None); self.misses+=1; owner=True
            else: event,_=old; self.hits+=1; owner=False
        if owner:
            with conn() as db:
                with db.cursor() as cur: value=common_read(cur,w,d,c)
            time.sleep(self.ms/1000)
            with self.mu: self.data[task]=(event,value)
            event.set()
        else: event.wait()
        with self.mu: return self.data[task][1]


def run(args) -> None:
    jobs=[job(t,k,args) for t in range(args.tasks) for k in range(args.candidates)]; random.Random(args.seed).shuffle(jobs)
    cache=Cache(args.discovery_ms) if args.mode == "reuse" else None
    def work(j):
        if args.mode == "2pl": return two_pl(j,args)
        return occ(j,args,cache.get(j[0],j[3],j[4],j[5]) if cache else None)
    started=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex: rows=list(ex.map(work,jobs))
    elapsed=time.perf_counter()-started
    with conn() as db:
        with db.cursor() as cur:
            cur.execute("SELECT count(*) FROM tpcc_derived.stock WHERE s_quantity<0"); negative=cur.fetchone()[0]
    if negative: raise RuntimeError("negative inventory")
    l=[x.latency_ms for x in rows]
    out={"workload":"tpcc-derived-new-order","mode":args.mode,"seed":args.seed,"workers":args.workers,"tasks":args.tasks,"candidates_per_task":args.candidates,"hot_items":args.hot_items,"operations":len(rows),"committed":sum(x.ok for x in rows),"failed":sum(not x.ok for x in rows),"aborts":sum(x.aborts for x in rows),"throughput_ops_s":len(rows)/elapsed,"latency_ms":{"p50":statistics.median(l),"p95":statistics.quantiles(l,n=100,method="inclusive")[94]},"lock_wait_ms_total":sum(x.lock_wait_ms for x in rows),"discovery_executions":cache.misses if cache else len(rows),"discovery_reuse_hits":cache.hits if cache else 0}
    RESULTS.mkdir(exist_ok=True); path=RESULTS / f"tpcc_{args.mode}_w{args.workers}_c{args.candidates}_h{args.hot_items}_s{args.seed}.json"; path.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,indent=2)); print(f"raw result: {path}")


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True); setup_p=sub.add_parser("setup"); run_p=sub.add_parser("run")
    for q in (setup_p,run_p):
        q.add_argument("--warehouses",type=int,default=4); q.add_argument("--districts",type=int,default=4); q.add_argument("--customers",type=int,default=50); q.add_argument("--items",type=int,default=100)
    run_p.add_argument("--mode",choices=("2pl","occ","reuse"),required=True); run_p.add_argument("--workers",type=int,default=4); run_p.add_argument("--tasks",type=int,default=30); run_p.add_argument("--candidates",type=int,default=4); run_p.add_argument("--hot-items",type=int,default=2); run_p.add_argument("--discovery-ms",type=int,default=20); run_p.add_argument("--think-ms",type=int,default=5); run_p.add_argument("--seed",type=int,default=1)
    a=p.parse_args(); setup(a) if a.cmd=="setup" else run(a)
if __name__ == "__main__": main()
