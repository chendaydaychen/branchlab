"""Reproducible 2PL and OCC benchmark for multi-candidate transactions."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import random
import statistics
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import psycopg
from psycopg import errors


DSN = "postgresql://branchlab:branchlab@localhost:55432/branchlab"
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


@dataclass
class CandidateResult:
    committed: bool
    attempts: int
    aborts: int
    latency_ms: float
    lock_wait_ms: float = 0.0


class SafeOrderCache:
    """One task-scoped discovery future, checked again by OCC at commit."""
    def __init__(self, discovery_ms: int):
        self.discovery_ms = discovery_ms
        self.lock = threading.Lock()
        self.entries = {}
        self.misses = 0
        self.hits = 0

    def get(self, task_id: int, order_id: int):
        with self.lock:
            item = self.entries.get(task_id)
            if item is None:
                event = threading.Event()
                self.entries[task_id] = (event, None)
                self.misses += 1
                owner = True
            else:
                event, _ = item
                self.hits += 1
                owner = False
        if owner:
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT row_version FROM users WHERE user_id=%s", (order_id,))
                    value = cur.fetchone()
            time.sleep(self.discovery_ms / 1000)
            with self.lock:
                self.entries[task_id] = (event, value)
            event.set()
        else:
            event.wait()
        with self.lock:
            return self.entries[task_id][1]


def connect():
    return psycopg.connect(DSN, autocommit=False)


def setup() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute((ROOT / "branchlab" / "schema.sql").read_text())
            cur.executemany(
                "INSERT INTO users (user_id, loyalty_tier) VALUES (%s, %s)",
                [(i, i % 4) for i in range(1, 1001)],
            )
            cur.executemany(
                "INSERT INTO flights (flight_id, price_cents, seats_left) VALUES (%s, %s, %s)",
                [(i, 10_000 + i * 37, 10_000) for i in range(1, 129)],
            )
            cur.executemany(
                "INSERT INTO orders (order_id, user_id, flight_id, status) VALUES (%s, %s, %s, 'confirmed')",
                [(i, i, (i % 128) + 1) for i in range(1, 1001)],
            )
        conn.commit()
    print("database initialized: 1000 users/orders, 128 flights")


def candidate_rows(task_id: int, candidate: int, hot_flights: int) -> tuple[int, int, int, str]:
    """Same common discovery phase; branch-specific target and final action."""
    order_id = (task_id % 1000) + 1
    target_flight = ((task_id * 17 + candidate * 7) % hot_flights) + 1
    action = ("rebook", "cancel_rebook", "split")[candidate % 3]
    return order_id, target_flight, candidate, action


def run_2pl(order_id: int, flight_id: int, action: str, discovery_ms: int, think_ms: int) -> CandidateResult:
    started = time.perf_counter()
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                before_lock = time.perf_counter()
                # A global lock order prevents deadlocks from dominating the comparison.
                cur.execute("SELECT row_version FROM users WHERE user_id=%s FOR UPDATE", (order_id,))
                cur.fetchone()
                cur.execute(
                    "SELECT flight_id, seats_left, price_cents FROM flights WHERE flight_id = %s FOR UPDATE",
                    (flight_id,),
                )
                flight = cur.fetchone()
                cur.execute(
                    "SELECT order_id, user_id, flight_id, status FROM orders WHERE order_id = %s FOR UPDATE",
                    (order_id,),
                )
                order = cur.fetchone()
                lock_wait = (time.perf_counter() - before_lock) * 1000
                if not order or not flight or flight[1] <= 0:
                    conn.rollback()
                    return CandidateResult(False, 1, 0, (time.perf_counter() - started) * 1000, lock_wait)
                time.sleep((discovery_ms + think_ms) / 1000)
                if action == "split":
                    cur.execute("UPDATE orders SET status='split', row_version=row_version+1 WHERE order_id=%s", (order_id,))
                else:
                    cur.execute(
                        "UPDATE flights SET seats_left=seats_left-1, row_version=row_version+1 WHERE flight_id=%s",
                        (flight_id,),
                    )
                    cur.execute(
                        "UPDATE orders SET flight_id=%s, status='confirmed', row_version=row_version+1 WHERE order_id=%s",
                        (flight_id, order_id),
                    )
                conn.commit()
        return CandidateResult(True, 1, 0, (time.perf_counter() - started) * 1000, lock_wait)
    except errors.DeadlockDetected:
        return CandidateResult(False, 1, 1, (time.perf_counter() - started) * 1000)


def run_occ(order_id: int, flight_id: int, action: str, discovery_ms: int, think_ms: int, cached_order=None, max_retries: int = 12) -> CandidateResult:
    started = time.perf_counter()
    aborts = 0
    for attempt in range(1, max_retries + 1):
        try:
            with connect() as conn:
                with conn.cursor() as cur:
                    if cached_order is not None and attempt == 1:
                        user_version = cached_order[0]
                    else:
                        cur.execute("SELECT row_version FROM users WHERE user_id=%s", (order_id,))
                        user_version = cur.fetchone()[0]
                    cur.execute("SELECT row_version FROM orders WHERE order_id=%s", (order_id,))
                    order = cur.fetchone()
                    cur.execute("SELECT seats_left, row_version FROM flights WHERE flight_id=%s", (flight_id,))
                    flight = cur.fetchone()
                    if not order or not flight or flight[0] <= 0:
                        conn.rollback()
                        return CandidateResult(False, attempt, aborts, (time.perf_counter() - started) * 1000)
                    order_version, flight_version = order[0], flight[1]
                    time.sleep((think_ms + (0 if cached_order is not None and attempt == 1 else discovery_ms)) / 1000)
                    # Validation and writes form the commit phase.  Version predicates
                    # validate precisely the rows read by this candidate.
                    # Validate the complete read set.  Even `split` only reads a
                    # flight, so it performs a no-op versioned update that locks and
                    # validates that row during the commit phase.
                    cur.execute("SELECT row_version FROM users WHERE user_id=%s FOR UPDATE", (order_id,))
                    if cur.fetchone()[0] != user_version:
                        conn.rollback()
                        aborts += 1
                        continue
                    cur.execute(
                        "UPDATE flights SET seats_left=seats_left-%s, row_version=row_version+%s "
                        "WHERE flight_id=%s AND row_version=%s AND seats_left>=%s",
                        (0 if action == "split" else 1, 0 if action == "split" else 1,
                         flight_id, flight_version, 0 if action == "split" else 1),
                    )
                    if cur.rowcount != 1:
                        conn.rollback()
                        aborts += 1
                        continue
                    cur.execute(
                        "UPDATE orders SET flight_id=%s, status=%s, row_version=row_version+1 "
                        "WHERE order_id=%s AND row_version=%s",
                        (flight_id, "split" if action == "split" else "confirmed", order_id, order_version),
                    )
                    if cur.rowcount != 1:
                        conn.rollback()
                        aborts += 1
                        continue
                    conn.commit()
                    return CandidateResult(True, attempt, aborts, (time.perf_counter() - started) * 1000)
        except errors.SerializationFailure:
            aborts += 1
    return CandidateResult(False, max_retries, aborts, (time.perf_counter() - started) * 1000)


def validate() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM flights WHERE seats_left < 0")
            negative = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM orders WHERE status NOT IN ('confirmed', 'cancelled', 'split')")
            invalid = cur.fetchone()[0]
    if negative or invalid:
        raise RuntimeError(f"invariant failure: negative_seats={negative}, invalid_orders={invalid}")


def percentile(values: list[float], p: float) -> float:
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[int(p) - 1]


def run(args: argparse.Namespace) -> None:
    random.seed(args.seed)
    started = time.perf_counter()
    jobs = []
    for task_id in range(args.tasks):
        for candidate in range(args.candidates):
            order_id, flight_id, _, action = candidate_rows(task_id, candidate, args.hot_flights)
            jobs.append((task_id, order_id, flight_id, action))
    random.shuffle(jobs)
    cache = SafeOrderCache(args.discovery_ms) if args.mode == "reuse" else None

    def execute(job):
        task_id, order_id, flight_id, action = job
        if args.mode == "2pl":
            return run_2pl(order_id, flight_id, action, args.discovery_ms, args.think_ms)
        cached = cache.get(task_id, order_id) if cache else None
        return run_occ(order_id, flight_id, action, args.discovery_ms, args.think_ms, cached)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(execute, job) for job in jobs]
        rows = [future.result() for future in futures]
    elapsed = time.perf_counter() - started
    validate()
    latencies = [row.latency_ms for row in rows]
    payload = {
        "mode": args.mode,
        "seed": args.seed,
        "workers": args.workers,
        "tasks": args.tasks,
        "candidates_per_task": args.candidates,
        "hot_flights": args.hot_flights,
        "think_ms": args.think_ms,
        "discovery_ms": args.discovery_ms,
        "operations": len(rows),
        "committed": sum(row.committed for row in rows),
        "failed": sum(not row.committed for row in rows),
        "aborts": sum(row.aborts for row in rows),
        "retry_rate": sum(row.aborts for row in rows) / len(rows),
        "throughput_ops_s": len(rows) / elapsed,
        "elapsed_s": elapsed,
        "latency_ms": {"p50": statistics.median(latencies), "p95": percentile(latencies, 95), "mean": statistics.mean(latencies)},
        "lock_wait_ms_total": sum(row.lock_wait_ms for row in rows),
        "discovery_executions": cache.misses if cache else len(rows),
        "discovery_reuse_hits": cache.hits if cache else 0,
    }
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / ("%s_w%d_c%d_h%d_s%d.json" % (args.mode, args.workers, args.candidates, args.hot_flights, args.seed))
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    print(f"raw result: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--mode", choices=("2pl", "occ", "reuse"), required=True)
    run_parser.add_argument("--workers", type=int, required=True)
    run_parser.add_argument("--candidates", type=int, required=True)
    run_parser.add_argument("--tasks", type=int, required=True)
    run_parser.add_argument("--hot-flights", type=int, required=True)
    run_parser.add_argument("--think-ms", type=int, default=5)
    run_parser.add_argument("--discovery-ms", type=int, default=8)
    run_parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    setup() if args.command == "setup" else run(args)


if __name__ == "__main__":
    main()
