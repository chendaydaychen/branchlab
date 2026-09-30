"""Collect and execute read-only DeepSeek candidate SQL on BIRD-Interact Lite.

This is deliberately a trajectory collector, not an official BIRD scorer: the
public Lite release does not contain ground-truth SQL or executable test cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import psycopg

from .deepseek_client import complete


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "vendor" / "bird-interact-lite"
OUT = ROOT / "results" / "bird_lite_trajectories"
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|grant|revoke|copy|call|do)\b", re.I)


def load_task(instance_id: str) -> dict:
    with (DATA / "bird_interact_data.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["instance_id"] == instance_id:
                return row
    raise KeyError(f"BIRD Lite task not found: {instance_id}")


def candidate_sql(task: dict, count: int) -> list[str]:
    database = task["selected_database"]
    schema = (DATA / database / f"{database}_schema.txt").read_text(encoding="utf-8")
    kb_path = DATA / database / f"{database}_kb.jsonl"
    knowledge = "\n".join(kb_path.read_text(encoding="utf-8").splitlines()[:12])
    system = "Return only JSON. You write PostgreSQL SELECT queries only; do not modify data."
    prompt = (
        f"Task: {task['amb_user_query']}\n\nSchema:\n{schema}\n\nRelevant knowledge examples:\n{knowledge}\n\n"
        f"Return {{\"candidates\":[{{\"sql\":\"...\"}}]}} with exactly {count} distinct executable SQL candidates."
    )
    reply = json.loads(complete([{"role": "system", "content": system}, {"role": "user", "content": prompt}], max_tokens=1800))
    sqls = [item.get("sql", "").strip() for item in reply.get("candidates", [])]
    if len(sqls) != count:
        raise ValueError("model did not return the requested candidate count")
    if any(not sql.lower().lstrip().startswith(("select", "with")) or FORBIDDEN.search(sql) for sql in sqls):
        raise ValueError("candidate set contains a non-read-only statement")
    return sqls


def execute(database: str, sql: str) -> dict:
    started = time.perf_counter()
    dsn = f"postgresql://root:123123@localhost:55433/{database}_template"
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '15000ms'")
                cur.execute(sql)
                rows = cur.fetchmany(5)
                columns = [d.name for d in cur.description] if cur.description else []
        return {"ok": True, "latency_ms": (time.perf_counter() - started) * 1000, "columns": columns, "sample_rows": [list(r) for r in rows]}
    except Exception as exc:
        return {"ok": False, "latency_ms": (time.perf_counter() - started) * 1000, "error": type(exc).__name__, "message": str(exc)[:400]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", default="alien_1")
    parser.add_argument("--candidates", type=int, default=4)
    args = parser.parse_args()
    task = load_task(args.instance_id)
    sqls = candidate_sql(task, args.candidates)
    seen: set[str] = set()
    results = []
    for sql in sqls:
        fingerprint = hashlib.sha256(" ".join(sql.split()).encode()).hexdigest()[:16]
        duplicate = fingerprint in seen
        seen.add(fingerprint)
        results.append({"fingerprint": fingerprint, "duplicate": duplicate, "sql": sql, "execution": execute(task["selected_database"], sql)})
    payload = {"instance_id": args.instance_id, "database": task["selected_database"], "candidate_count": len(results), "unique_candidates": len(seen), "public_gt_available": bool(task.get("test_cases")), "results": results}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{args.instance_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"instance_id": args.instance_id, "unique_candidates": len(seen), "executed_ok": sum(r["execution"]["ok"] for r in results), "output": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
