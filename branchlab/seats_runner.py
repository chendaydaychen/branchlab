"""SEATS-derived candidate reservation experiment; not an official SEATS run."""
from __future__ import annotations
import argparse, concurrent.futures, json, math, random, statistics, threading, time
from dataclasses import dataclass
from pathlib import Path
import psycopg
from branchlab.task_semantics import SeatReservationSemantic
DSN = "postgresql://branchlab:branchlab@localhost:55432/branchlab"
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SEATS_PER_FLIGHT = 150
MODES = (
    "2pl",
    "occ",
    "reuse_strict",
    "semantic_occ",
    "semantic_reuse",
    "pg_rc",
    "pg_rr",
    "pg_ssi",
)
@dataclass(frozen=True)
class Flight: fid: str; left: int; version: int; price: float
@dataclass
class Result: ok: bool; aborts: int; latency: float; lock_wait: float = 0.0
def conn(isolation: str | None = None):
    db = psycopg.connect(DSN, autocommit=False)
    if isolation is not None:
        db.isolation_level = getattr(psycopg.IsolationLevel, isolation)
    return db
def setup(a):
    with conn() as db, db.cursor() as c:
        c.execute((ROOT / "seats_derived" / "schema.sql").read_text())
        c.executemany("INSERT INTO seats_derived.flight VALUES(%s,100,150,150,0)", [(f"F{n:03d}",) for n in range(1,a.flights+1)])
        c.executemany("INSERT INTO seats_derived.customer(c_id) VALUES(%s)", [(f"C{n:05d}",) for n in range(1,a.customers+1)])
        db.commit()
    print(f"initialized SEATS-derived flights={a.flights}, customers={a.customers}")
def read(c,fid,lock=False):
    c.execute("SELECT f_seats_left,row_version,f_base_price FROM seats_derived.flight WHERE f_id=%s"+(" FOR UPDATE" if lock else ""),(fid,))
    row=c.fetchone()
    if not row: raise RuntimeError("missing flight")
    return Flight(fid,*row)
def valid(c,x,semantic=False):
    c.execute("SELECT f_seats_left,row_version,f_base_price FROM seats_derived.flight WHERE f_id=%s FOR UPDATE",(x.fid,))
    left,version,price=c.fetchone()
    if not semantic:
        return left > 0, version
    verdict = SeatReservationSemantic().validate(
        {"row_version": x.version, "seats_left": x.left, "price": x.price},
        {"row_version": version, "seats_left": left, "price": price},
    )
    return verdict.acceptable, verdict.rebased_version
def job(t,k,a):
    # Tasks are striped across hot flights. Use the task's ordinal within its
    # flight for the winning seat, so longer runs do not wrap after 75 tasks
    # when candidates=4. Candidate offsets keep alternatives distinct.
    flight_ordinal = t // a.hot_flights
    tasks_per_flight = math.ceil(a.tasks / a.hot_flights)
    seat = (flight_ordinal + k * tasks_per_flight) % SEATS_PER_FLIGHT
    return t,k,t*1000+k,f"F{(t%a.hot_flights)+1:03d}",f"C{(t*a.candidates+k)%a.customers+1:05d}",seat
def commit(c,x,j,winner_only,semantic=False):
    t,k,b,fid,cid,seat=j
    acceptable,current_version = valid(c,x,semantic)
    if not acceptable or (not semantic and current_version != x.version): return False
    # In an agentic task, only the selected candidate may materialize the
    # external reservation. Other branches still validate their shared read
    # and write an isolated audit record.
    if winner_only and k != 0:
        c.execute("INSERT INTO seats_derived.branch_commit(branch_id,task_id,candidate_id,f_id) VALUES(%s,%s,%s,%s)",(b,t,k,fid))
        return True
    c.execute("INSERT INTO seats_derived.reservation(r_id,r_c_id,r_f_id,r_seat,r_price) VALUES(%s,%s,%s,%s,%s)",(b,cid,fid,seat,x.price))
    c.execute("UPDATE seats_derived.flight SET f_seats_left=f_seats_left-1,row_version=row_version+1 WHERE f_id=%s AND row_version=%s AND f_seats_left>0",(fid,current_version))
    if c.rowcount!=1: return False
    c.execute("UPDATE seats_derived.customer SET reservations=reservations+1 WHERE c_id=%s",(cid,))
    c.execute("INSERT INTO seats_derived.branch_commit(branch_id,task_id,candidate_id,f_id) VALUES(%s,%s,%s,%s)",(b,t,k,fid))
    return True

def commit_native(c,x,j,winner_only):
    """Materialize using only the selected PostgreSQL isolation level.

    Unlike OCC, this path performs no application-level row-version check.
    Database serialization failures are handled by ``pg_native``.
    """
    t,k,b,fid,cid,seat=j
    if winner_only and k != 0:
        c.execute("INSERT INTO seats_derived.branch_commit(branch_id,task_id,candidate_id,f_id) VALUES(%s,%s,%s,%s)",(b,t,k,fid))
        return True
    c.execute("INSERT INTO seats_derived.reservation(r_id,r_c_id,r_f_id,r_seat,r_price) VALUES(%s,%s,%s,%s,%s)",(b,cid,fid,seat,x.price))
    c.execute("UPDATE seats_derived.flight SET f_seats_left=f_seats_left-1,row_version=row_version+1 WHERE f_id=%s AND f_seats_left>0",(fid,))
    if c.rowcount!=1: return False
    c.execute("UPDATE seats_derived.customer SET reservations=reservations+1 WHERE c_id=%s",(cid,))
    c.execute("INSERT INTO seats_derived.branch_commit(branch_id,task_id,candidate_id,f_id) VALUES(%s,%s,%s,%s)",(b,t,k,fid))
    return True
def two_pl(j,a):
    start=time.perf_counter()
    with conn() as db,db.cursor() as c:
        ws=time.perf_counter(); x=read(c,j[3],True); wait=(time.perf_counter()-ws)*1000
        time.sleep((a.discovery_ms+a.think_ms)/1000); ok=commit(c,x,j,a.winner_only); (db.commit if ok else db.rollback)()
    return Result(ok,0 if ok else 1,(time.perf_counter()-start)*1000,wait)
def occ(j,a,cached=None,semantic=False):
    start=time.perf_counter(); aborts=0
    for attempt in range(a.retries):
        try:
            with conn() as db,db.cursor() as c:
                x=cached if cached is not None and attempt==0 else read(c,j[3])
                if cached is None or attempt: time.sleep(a.discovery_ms/1000)
                time.sleep(a.think_ms/1000)
                if commit(c,x,j,a.winner_only,semantic): db.commit(); return Result(True,aborts,(time.perf_counter()-start)*1000)
                db.rollback()
        except psycopg.errors.UniqueViolation: pass
        aborts+=1
    return Result(False,aborts,(time.perf_counter()-start)*1000)

def pg_native(j,a,isolation):
    start=time.perf_counter(); aborts=0
    for _ in range(a.retries):
        try:
            with conn(isolation) as db,db.cursor() as c:
                x=read(c,j[3])
                time.sleep(a.discovery_ms/1000)
                time.sleep(a.think_ms/1000)
                if commit_native(c,x,j,a.winner_only):
                    db.commit(); return Result(True,aborts,(time.perf_counter()-start)*1000)
                db.rollback()
        except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected, psycopg.errors.UniqueViolation):
            pass
        aborts+=1
    return Result(False,aborts,(time.perf_counter()-start)*1000)
class Cache:
    def __init__(self,ms): self.ms,self.mu,self.data,self.hits,self.misses=ms,threading.Lock(),{},0,0
    def get(self,t,fid):
        with self.mu:
            old=self.data.get(t)
            if old is None: e=threading.Event(); self.data[t]=(e,None); self.misses+=1; own=True
            else: e,_=old; self.hits+=1; own=False
        if own:
            with conn() as db,db.cursor() as c: x=read(c,fid)
            time.sleep(self.ms/1000)
            with self.mu: self.data[t]=(e,x)
            e.set()
        else: e.wait()
        with self.mu: return self.data[t][1]
def run(a):
    if math.ceil(a.tasks / a.hot_flights) > SEATS_PER_FLIGHT:
        raise ValueError(
            f"tasks per hot flight exceed the {SEATS_PER_FLIGHT}-seat workload capacity; "
            "increase --hot-flights or reduce --tasks"
        )
    if a.winner_only:
        # Phase 1 evaluates every non-winning branch. Phase 2 materializes the
        # one selected branch, preventing an early winner from invalidating
        # sibling snapshots before selection is complete.
        jobs=[job(t,k,a) for k in range(1,a.candidates) for t in range(a.tasks)]
        jobs += [job(t,0,a) for t in range(a.tasks)]
    else:
        jobs=[job(t,k,a) for t in range(a.tasks) for k in range(a.candidates)]
        random.Random(a.seed).shuffle(jobs)
    cache=Cache(a.discovery_ms) if a.mode in ("reuse_strict","semantic_reuse") else None
    def work(j):
        if a.mode=="2pl": return two_pl(j,a)
        if a.mode=="pg_rc": return pg_native(j,a,"READ_COMMITTED")
        if a.mode=="pg_rr": return pg_native(j,a,"REPEATABLE_READ")
        if a.mode=="pg_ssi": return pg_native(j,a,"SERIALIZABLE")
        return occ(j,a,cache.get(j[0],j[3]) if cache else None,a.mode in ("semantic_occ","semantic_reuse"))
    started=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex: rows=list(ex.map(work,jobs))
    elapsed=time.perf_counter()-started; l=[r.latency for r in rows]
    with conn() as db, db.cursor() as c:
        c.execute("SELECT COALESCE(sum(f_seats_total-f_seats_left),0), (SELECT count(*) FROM seats_derived.reservation) FROM seats_derived.flight")
        sold, reservations = c.fetchone()
        c.execute("SELECT COALESCE(sum(reservations),0) FROM seats_derived.customer")
        customer_reservations = c.fetchone()[0]
    invariant_violations = int(sold != reservations) + int(reservations != customer_reservations)
    if invariant_violations:
        raise RuntimeError(f"SEATS invariant violation: sold={sold}, reservations={reservations}, customer_count={customer_reservations}")
    committed=sum(r.ok for r in rows)
    out={"workload":"seats-derived-candidate-reservation","official_benchmark_result":False,"mode":a.mode,"semantic_validation":a.mode in ("semantic_occ","semantic_reuse"),"shared_prefix_reuse":cache is not None,"winner_only":a.winner_only,"seed":a.seed,"workers":a.workers,"tasks":a.tasks,"candidates_per_task":a.candidates,"hot_flights":a.hot_flights,"discovery_ms":a.discovery_ms,"think_ms":a.think_ms,"retry_limit":a.retries,"operations":len(rows),"committed":committed,"failed":sum(not r.ok for r in rows),"aborts":sum(r.aborts for r in rows),"elapsed_s":elapsed,"throughput_ops_s":len(rows)/elapsed,"goodput_ops_s":committed/elapsed,"success_rate":committed/len(rows),"latency_ms":{"p50":statistics.median(l),"p95":statistics.quantiles(l,n=100,method="inclusive")[94],"p99":statistics.quantiles(l,n=100,method="inclusive")[98]},"lock_wait_ms_total":sum(r.lock_wait for r in rows),"discovery_executions":cache.misses if cache else len(rows),"discovery_reuse_hits":cache.hits if cache else 0,"invariant_violations":invariant_violations}
    RESULTS.mkdir(exist_ok=True); suffix=f"_{a.result_tag}" if a.result_tag else ""; path=RESULTS/f"seats_{a.mode}_w{a.workers}_c{a.candidates}_h{a.hot_flights}_s{a.seed}{suffix}.json"; path.write_text(json.dumps(out,indent=2)+"\n"); print(json.dumps(out,indent=2)); print(path)
def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True); q=s.add_parser("setup"); r=s.add_parser("run")
    q.add_argument("--flights",type=int,default=32); q.add_argument("--customers",type=int,default=1000)
    r.add_argument("--mode",choices=MODES,required=True); r.add_argument("--workers",type=int,default=8); r.add_argument("--tasks",type=int,default=40); r.add_argument("--candidates",type=int,default=4); r.add_argument("--customers",type=int,default=1000); r.add_argument("--hot-flights",type=int,default=16); r.add_argument("--discovery-ms",type=int,default=20); r.add_argument("--think-ms",type=int,default=10); r.add_argument("--retries",type=int,default=12); r.add_argument("--winner-only",action="store_true"); r.add_argument("--seed",type=int,default=1); r.add_argument("--result-tag",default="")
    a=p.parse_args(); setup(a) if a.cmd=="setup" else run(a)
if __name__=="__main__": main()
