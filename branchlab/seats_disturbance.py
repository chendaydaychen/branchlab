"""Adversarial state-change tests against the real SEATS commit path."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from types import SimpleNamespace
import psycopg
from branchlab.seats_runner import ROOT, RESULTS, commit, conn, read, setup

def external_reservation(fid: str, cid: str, rid: int, seat: int, *, total: int | None = None) -> None:
    with conn() as db, db.cursor() as cur:
        if total is not None:
            cur.execute("UPDATE seats_derived.flight SET f_seats_total=%s WHERE f_id=%s", (total, fid))
        cur.execute("INSERT INTO seats_derived.reservation(r_id,r_c_id,r_f_id,r_seat,r_price) VALUES(%s,%s,%s,%s,100)", (rid,cid,fid,seat))
        cur.execute("UPDATE seats_derived.flight SET f_seats_left=f_seats_left-1,row_version=row_version+1 WHERE f_id=%s", (fid,))
        cur.execute("UPDATE seats_derived.customer SET reservations=reservations+1 WHERE c_id=%s", (cid,))
        db.commit()

def try_commit(observed, job, semantic: bool) -> bool:
    try:
        with conn() as db, db.cursor() as cur:
            accepted = commit(cur, observed, job, False, semantic)
            (db.commit if accepted else db.rollback)()
            return accepted
    except psycopg.errors.UniqueViolation:
        return False

def run(repetitions: int) -> dict:
    setup(SimpleNamespace(flights=repetitions*5, customers=repetitions*10))
    counts = {name: 0 for name in ("semantic_rebase_accept","strict_version_reject","over_budget_reject","sold_out_reject","duplicate_seat_reject")}
    false_accepts = false_rejects = 0
    for i in range(repetitions):
        # Changed version and capacity, but the task remains feasible.
        fid=f"F{i+1:03d}"; cid=f"C{i+1:05d}"; ext=f"C{i+repetitions*5+1:05d}"
        with conn() as db, db.cursor() as cur: observed=read(cur,fid)
        external_reservation(fid,ext,1_000_000+i,149)
        accepted=try_commit(observed,(i,0,2_000_000+i,fid,cid,0),True)
        counts["semantic_rebase_accept"] += int(accepted); false_rejects += int(not accepted)

        # The same benign version change must be rejected by strict OCC.
        n=repetitions+i; fid=f"F{n+1:03d}"; cid=f"C{n+1:05d}"; ext=f"C{n+repetitions*5+1:05d}"
        with conn() as db, db.cursor() as cur: observed=read(cur,fid)
        external_reservation(fid,ext,3_000_000+i,149)
        rejected=not try_commit(observed,(n,0,4_000_000+i,fid,cid,0),False)
        counts["strict_version_reject"] += int(rejected); false_accepts += int(not rejected)

        # Price crosses the hard budget.
        n=2*repetitions+i; fid=f"F{n+1:03d}"; cid=f"C{n+1:05d}"
        with conn() as db, db.cursor() as cur: observed=read(cur,fid)
        with conn() as db, db.cursor() as cur:
            cur.execute("UPDATE seats_derived.flight SET f_base_price=121,row_version=row_version+1 WHERE f_id=%s",(fid,)); db.commit()
        rejected=not try_commit(observed,(n,0,5_000_000+i,fid,cid,0),True)
        counts["over_budget_reject"] += int(rejected); false_accepts += int(not rejected)

        # A one-seat flight is exhausted by another transaction.
        n=3*repetitions+i; fid=f"F{n+1:03d}"; cid=f"C{n+1:05d}"; ext=f"C{n+repetitions*5+1:05d}"
        with conn() as db, db.cursor() as cur: observed=read(cur,fid)
        with conn() as db, db.cursor() as cur:
            cur.execute("UPDATE seats_derived.flight SET f_seats_total=1,f_seats_left=1 WHERE f_id=%s",(fid,)); db.commit()
        external_reservation(fid,ext,6_000_000+i,0)
        rejected=not try_commit(observed,(n,0,7_000_000+i,fid,cid,1),True)
        counts["sold_out_reject"] += int(rejected); false_accepts += int(not rejected)

        # Capacity remains, but the exact selected seat is already occupied.
        n=4*repetitions+i; fid=f"F{n+1:03d}"; cid=f"C{n+1:05d}"; ext=f"C{n+repetitions*5+1:05d}"
        with conn() as db, db.cursor() as cur: observed=read(cur,fid)
        external_reservation(fid,ext,8_000_000+i,0)
        rejected=not try_commit(observed,(n,0,9_000_000+i,fid,cid,0),True)
        counts["duplicate_seat_reject"] += int(rejected); false_accepts += int(not rejected)
    with conn() as db, db.cursor() as cur:
        cur.execute("SELECT COALESCE(sum(f_seats_total-f_seats_left),0),(SELECT count(*) FROM seats_derived.reservation) FROM seats_derived.flight")
        sold,reservations=cur.fetchone()
        cur.execute("SELECT COALESCE(sum(reservations),0) FROM seats_derived.customer")
        customer_count=cur.fetchone()[0]
    result={"repetitions_per_case":repetitions,**counts,"false_accepts":false_accepts,"false_rejects":false_rejects,
            "semantic_violations":false_accepts,"business_invariant_violations":int(sold!=reservations)+int(reservations!=customer_count)}
    RESULTS.mkdir(exist_ok=True)
    path=RESULTS/"seats_semantic_disturbance.json"; path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2)); print(path)
    if false_accepts or false_rejects or result["business_invariant_violations"]: raise RuntimeError("semantic disturbance test failed")
    return result

def main():
    p=argparse.ArgumentParser(); p.add_argument("--repetitions",type=int,default=100); a=p.parse_args(); run(a.repetitions)
if __name__=="__main__": main()
