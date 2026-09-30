"""TATP-derived speculative UpdateLocation workload (not an official TATP run)."""
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
from branchlab.task_semantics import SubscriberLocationSemantic

DSN = "postgresql://branchlab:branchlab@localhost:55432/branchlab"
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

@dataclass(frozen=True)
class Common:
    subscriber_id: int
    subscriber_version: int
    access_version: int

@dataclass
class Outcome:
    ok: bool
    aborts: int
    latency_ms: float
    lock_wait_ms: float = 0.0

def dbconn():
    return psycopg.connect(DSN, autocommit=False)

def setup(args) -> None:
    with dbconn() as db, db.cursor() as cur:
        cur.execute((ROOT / "tatp_derived" / "schema.sql").read_text())
        cur.executemany("INSERT INTO tatp_derived.subscriber(s_id,sub_nbr,msc_location,vlr_location) VALUES(%s,%s,%s,%s)",
            [(sid, f"{sid:015d}", sid * 10, sid * 100) for sid in range(1, args.subscribers + 1)])
        cur.executemany("INSERT INTO tatp_derived.access_info(s_id,ai_type,data1,data2,data3,data4) VALUES(%s,1,%s,%s,'abc','data')",
            [(sid, sid % 100, (sid * 3) % 100) for sid in range(1, args.subscribers + 1)])
        cur.executemany("INSERT INTO tatp_derived.special_facility(s_id,sf_type) VALUES(%s,1)",
            [(sid,) for sid in range(1, args.subscribers + 1)])
        db.commit()
    print(f"initialized TATP-derived subscribers={args.subscribers}")

def common_read(cur, subscriber_id: int, lock: bool = False) -> Common:
    suffix = " FOR UPDATE OF s, a" if lock else ""
    cur.execute("SELECT s.row_version,a.row_version FROM tatp_derived.subscriber s "
                "JOIN tatp_derived.access_info a ON a.s_id=s.s_id AND a.ai_type=1 "
                "WHERE s.s_id=%s" + suffix, (subscriber_id,))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("missing TATP-derived subscriber/access record")
    return Common(subscriber_id, *row)

def validate_common(cur, x: Common, semantic: bool = False) -> int | None:
    cur.execute("SELECT row_version FROM tatp_derived.subscriber WHERE s_id=%s FOR UPDATE", (x.subscriber_id,))
    subscriber = cur.fetchone()
    if subscriber is None:
        return None
    cur.execute("SELECT row_version FROM tatp_derived.access_info WHERE s_id=%s AND ai_type=1 FOR UPDATE", (x.subscriber_id,))
    access = cur.fetchone()
    if access is None:
        return None
    if not semantic:
        return subscriber[0] if subscriber[0] == x.subscriber_version and access[0] == x.access_version else None
    verdict = SubscriberLocationSemantic().validate(
        {"row_version": x.subscriber_version},
        {"row_version": subscriber[0], "subscriber_exists": True, "access_exists": True},
    )
    return verdict.rebased_version if verdict.acceptable else None

def branch(task: int, candidate: int, args):
    subscriber_id = (task % args.hot_subscribers) + 1
    return task, candidate, task * 1000 + candidate, subscriber_id, (task * 7919 + candidate * 101) % 1000000

def commit(cur, x: Common, branch_id: int, task: int, candidate: int, location: int, semantic: bool = False, winner_only: bool = False) -> bool:
    version = validate_common(cur, x, semantic)
    if version is None:
        return False
    if winner_only and candidate != 0:
        cur.execute("INSERT INTO tatp_derived.branch_commit(branch_id,task_id,candidate_id,s_id,action,materialized) "
                    "VALUES(%s,%s,%s,%s,'EvaluateLocation',false)", (branch_id, task, candidate, x.subscriber_id))
        return True
    cur.execute("UPDATE tatp_derived.subscriber SET vlr_location=%s,row_version=row_version+1 "
                "WHERE s_id=%s AND row_version=%s", (location, x.subscriber_id, version))
    if cur.rowcount != 1:
        return False
    cur.execute("INSERT INTO tatp_derived.branch_commit(branch_id,task_id,candidate_id,s_id,action,materialized) "
                "VALUES(%s,%s,%s,%s,'UpdateLocation',true)", (branch_id, task, candidate, x.subscriber_id))
    return True

def two_pl(j, args) -> Outcome:
    task, candidate, branch_id, subscriber_id, location = j
    started = time.perf_counter()
    with dbconn() as db, db.cursor() as cur:
        waited = time.perf_counter()
        x = common_read(cur, subscriber_id, lock=True)
        lock_wait = (time.perf_counter() - waited) * 1000
        time.sleep((args.discovery_ms + args.think_ms) / 1000)
        ok = commit(cur, x, branch_id, task, candidate, location, winner_only=args.winner_only)
        (db.commit if ok else db.rollback)()
    return Outcome(ok, 0 if ok else 1, (time.perf_counter() - started) * 1000, lock_wait)

def occ(j, args, cached: Common | None = None, semantic: bool = False) -> Outcome:
    task, candidate, branch_id, subscriber_id, location = j
    started, aborts = time.perf_counter(), 0
    for attempt in range(args.max_retries):
        with dbconn() as db, db.cursor() as cur:
            x = cached if cached is not None and attempt == 0 else common_read(cur, subscriber_id)
            if cached is None or attempt:
                time.sleep(args.discovery_ms / 1000)
            time.sleep(args.think_ms / 1000)
            if commit(cur, x, branch_id, task, candidate, location, semantic, args.winner_only):
                db.commit()
                return Outcome(True, aborts, (time.perf_counter() - started) * 1000)
            db.rollback()
            aborts += 1
    return Outcome(False, aborts, (time.perf_counter() - started) * 1000)

class TaskCache:
    def __init__(self, discovery_ms: int):
        self.discovery_ms, self.lock, self.items, self.hits, self.misses = discovery_ms, threading.Lock(), {}, 0, 0
    def get(self, task: int, subscriber_id: int) -> Common:
        with self.lock:
            item = self.items.get(task)
            if item is None:
                event = threading.Event()
                self.items[task] = (event, None)
                self.misses += 1
                owner = True
            else:
                event, _ = item
                self.hits += 1
                owner = False
        if owner:
            with dbconn() as db, db.cursor() as cur:
                value = common_read(cur, subscriber_id)
            time.sleep(self.discovery_ms / 1000)
            with self.lock:
                self.items[task] = (event, value)
            event.set()
        else:
            event.wait()
        with self.lock:
            return self.items[task][1]

def run(args) -> None:
    if args.winner_only:
        jobs = [branch(task, candidate, args) for candidate in range(1, args.candidates) for task in range(args.tasks)]
        jobs += [branch(task, 0, args) for task in range(args.tasks)]
    else:
        jobs = [branch(task, candidate, args) for task in range(args.tasks) for candidate in range(args.candidates)]
        random.Random(args.seed).shuffle(jobs)
    cache = TaskCache(args.discovery_ms) if args.mode in ("reuse_strict", "semantic_reuse") else None
    def work(j):
        if args.mode == "2pl":
            return two_pl(j, args)
        return occ(j, args, cache.get(j[0], j[3]) if cache else None, args.mode in ("semantic_occ", "semantic_reuse"))
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(work, jobs))
    elapsed = time.perf_counter() - started
    committed = sum(x.ok for x in rows)
    with dbconn() as db, db.cursor() as cur:
        cur.execute("SELECT count(*) FROM tatp_derived.branch_commit")
        audited = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM tatp_derived.branch_commit WHERE materialized")
        materialized = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(sum(row_version),0) FROM tatp_derived.subscriber")
        versions = cur.fetchone()[0]
    materialization_bound_broken = materialized > args.tasks if args.winner_only else materialized != committed
    invariant_violations = int(audited != committed) + int(materialization_bound_broken) + int(versions != materialized)
    if invariant_violations:
        raise RuntimeError(f"TATP invariant violation: audited={audited}, materialized={materialized}, versions={versions}, committed={committed}")
    latencies = [x.latency_ms for x in rows]
    out = {"workload": "tatp-derived-update-location", "official_benchmark_result": False, "mode": args.mode,
        "semantic_validation": args.mode in ("semantic_occ", "semantic_reuse"), "shared_prefix_reuse": cache is not None,
        "winner_only": args.winner_only, "materialized": materialized,
        "seed": args.seed, "workers": args.workers, "tasks": args.tasks, "candidates_per_task": args.candidates,
        "hot_subscribers": args.hot_subscribers, "operations": len(rows), "committed": committed,
        "failed": sum(not x.ok for x in rows), "aborts": sum(x.aborts for x in rows),
        "throughput_ops_s": len(rows) / elapsed,
        "discovery_ms": args.discovery_ms, "think_ms": args.think_ms, "retry_limit": args.max_retries,
        "latency_ms": {"p50": statistics.median(latencies), "p95": statistics.quantiles(latencies, n=100, method="inclusive")[94], "p99": statistics.quantiles(latencies, n=100, method="inclusive")[98]},
        "lock_wait_ms_total": sum(x.lock_wait_ms for x in rows),
        "discovery_executions": cache.misses if cache else len(rows),
        "discovery_reuse_hits": cache.hits if cache else 0, "invariant_violations": invariant_violations}
    RESULTS.mkdir(exist_ok=True)
    suffix = f"_{args.result_tag}" if args.result_tag else ""
    path = RESULTS / f"tatp_{args.mode}_w{args.workers}_c{args.candidates}_h{args.hot_subscribers}_s{args.seed}{suffix}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    print(f"raw result: {path}")

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    setup_p, run_p = commands.add_parser("setup"), commands.add_parser("run")
    setup_p.add_argument("--subscribers", type=int, default=100)
    run_p.add_argument("--mode", choices=("2pl", "occ", "reuse_strict", "semantic_occ", "semantic_reuse"), required=True)
    run_p.add_argument("--workers", type=int, default=8)
    run_p.add_argument("--tasks", type=int, default=40)
    run_p.add_argument("--candidates", type=int, default=4)
    run_p.add_argument("--hot-subscribers", type=int, default=1)
    run_p.add_argument("--discovery-ms", type=int, default=20)
    run_p.add_argument("--think-ms", type=int, default=10)
    run_p.add_argument("--max-retries", type=int, default=12)
    run_p.add_argument("--winner-only", action="store_true")
    run_p.add_argument("--result-tag", default="")
    run_p.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    setup(args) if args.command == "setup" else run(args)

if __name__ == "__main__":
    main()
