"""Database-level semantic disturbances for PostgreSQL isolation baselines."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import psycopg

from branchlab.seats_runner import RESULTS, commit, commit_native, conn, read, setup

CONTROLLERS = {
    "branchlab": None,
    "pg_rc": "READ_COMMITTED",
    "pg_rr": "REPEATABLE_READ",
    "pg_ssi": "SERIALIZABLE",
}


def change_price(fid: str, price: int) -> None:
    with conn() as db, db.cursor() as cur:
        cur.execute(
            "UPDATE seats_derived.flight SET f_base_price=%s,row_version=row_version+1 WHERE f_id=%s",
            (price, fid),
        )
        db.commit()


def semantic_attempt(fid: str, job: tuple, new_price: int) -> bool:
    with conn() as db, db.cursor() as cur:
        observed = read(cur, fid)
    change_price(fid, new_price)
    try:
        with conn() as db, db.cursor() as cur:
            accepted = commit(cur, observed, job, False, True)
            (db.commit if accepted else db.rollback)()
            return accepted
    except psycopg.errors.UniqueViolation:
        return False


def native_attempt(isolation: str, fid: str, job: tuple, new_price: int) -> bool:
    try:
        with conn(isolation) as db, db.cursor() as cur:
            observed = read(cur, fid)
            change_price(fid, new_price)
            accepted = commit_native(cur, observed, job, False)
            (db.commit if accepted else db.rollback)()
            return accepted
    except (
        psycopg.errors.SerializationFailure,
        psycopg.errors.DeadlockDetected,
        psycopg.errors.UniqueViolation,
    ):
        return False


def run(repetitions: int) -> dict:
    cases = ("benign_price_change", "over_budget_change")
    total = repetitions * len(CONTROLLERS) * len(cases)
    setup(SimpleNamespace(flights=total, customers=total + 10))
    result = {
        name: {
            case: {"accepted": 0, "rejected": 0, "false_accepts": 0, "false_rejects": 0}
            for case in cases
        }
        for name in CONTROLLERS
    }
    index = 0
    for controller, isolation in CONTROLLERS.items():
        for case in cases:
            new_price = 110 if case == "benign_price_change" else 121
            oracle = new_price <= 120
            for _ in range(repetitions):
                fid = f"F{index+1:03d}"
                cid = f"C{index+1:05d}"
                job = (index, 0, 10_000_000 + index, fid, cid, 0)
                accepted = (
                    semantic_attempt(fid, job, new_price)
                    if controller == "branchlab"
                    else native_attempt(isolation, fid, job, new_price)
                )
                row = result[controller][case]
                row["accepted"] += int(accepted)
                row["rejected"] += int(not accepted)
                row["false_accepts"] += int(accepted and not oracle)
                row["false_rejects"] += int(not accepted and oracle)
                index += 1
    output = {
        "repetitions_per_case": repetitions,
        "total_cases": total,
        "results": result,
    }
    path = RESULTS / "seats_native_semantic_disturbance.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    lines = [
        "# PostgreSQL isolation under semantic disturbances",
        "",
        f"Repetitions per controller/case: {repetitions}.",
        "",
        "| controller | disturbance | accepted | rejected | false accepts | false rejects |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for controller in CONTROLLERS:
        for case in cases:
            row = result[controller][case]
            lines.append(
                f"| {controller} | {case} | {row['accepted']} | {row['rejected']} | "
                f"{row['false_accepts']} | {row['false_rejects']} |"
            )
    report = RESULTS / "seats_native_semantic_disturbance.md"
    report.write_text("\n".join(lines) + "\n")
    print(json.dumps(output, indent=2))
    print(path)
    print(report)
    branchlab = result["branchlab"]
    if any(branchlab[case][metric] for case in cases for metric in ("false_accepts", "false_rejects")):
        raise RuntimeError("BranchLab diverged from the semantic oracle")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=100)
    args = parser.parse_args()
    run(args.repetitions)


if __name__ == "__main__":
    main()
