"""Adversarial state-change tests against the real TATP commit path."""
from __future__ import annotations
import argparse, json
from types import SimpleNamespace
from branchlab.tatp_runner import RESULTS, commit, common_read, dbconn, setup

def try_commit(observed, branch_id: int, location: int, semantic: bool) -> bool:
    with dbconn() as db, db.cursor() as cur:
        accepted=commit(cur,observed,branch_id,branch_id,0,location,semantic,False)
        (db.commit if accepted else db.rollback)()
        return accepted

def run(repetitions: int) -> dict:
    setup(SimpleNamespace(subscribers=repetitions*4))
    counts={name:0 for name in ("semantic_location_rebase","strict_version_reject","missing_access_reject","missing_subscriber_reject")}
    false_accepts=false_rejects=0
    for i in range(repetitions):
        sid=i+1
        with dbconn() as db,db.cursor() as cur: observed=common_read(cur,sid)
        with dbconn() as db,db.cursor() as cur:
            cur.execute("UPDATE tatp_derived.subscriber SET vlr_location=vlr_location+1,row_version=row_version+1 WHERE s_id=%s",(sid,)); db.commit()
        accepted=try_commit(observed,1_000_000+i,777,True)
        counts["semantic_location_rebase"]+=int(accepted); false_rejects+=int(not accepted)

        sid=repetitions+i+1
        with dbconn() as db,db.cursor() as cur: observed=common_read(cur,sid)
        with dbconn() as db,db.cursor() as cur:
            cur.execute("UPDATE tatp_derived.subscriber SET vlr_location=vlr_location+1,row_version=row_version+1 WHERE s_id=%s",(sid,)); db.commit()
        rejected=not try_commit(observed,2_000_000+i,777,False)
        counts["strict_version_reject"]+=int(rejected); false_accepts+=int(not rejected)

        sid=2*repetitions+i+1
        with dbconn() as db,db.cursor() as cur: observed=common_read(cur,sid)
        with dbconn() as db,db.cursor() as cur:
            cur.execute("DELETE FROM tatp_derived.access_info WHERE s_id=%s",(sid,)); db.commit()
        rejected=not try_commit(observed,3_000_000+i,777,True)
        counts["missing_access_reject"]+=int(rejected); false_accepts+=int(not rejected)

        sid=3*repetitions+i+1
        with dbconn() as db,db.cursor() as cur: observed=common_read(cur,sid)
        with dbconn() as db,db.cursor() as cur:
            cur.execute("DELETE FROM tatp_derived.access_info WHERE s_id=%s",(sid,))
            cur.execute("DELETE FROM tatp_derived.special_facility WHERE s_id=%s",(sid,))
            cur.execute("DELETE FROM tatp_derived.subscriber WHERE s_id=%s",(sid,)); db.commit()
        rejected=not try_commit(observed,4_000_000+i,777,True)
        counts["missing_subscriber_reject"]+=int(rejected); false_accepts+=int(not rejected)
    with dbconn() as db,db.cursor() as cur:
        cur.execute("SELECT count(*) FROM tatp_derived.branch_commit WHERE materialized")
        audit=cur.fetchone()[0]
        cur.execute("SELECT COALESCE(sum(row_version),0) FROM tatp_derived.subscriber")
        version_sum=cur.fetchone()[0]
    invariant_violations=int(audit!=repetitions)+int(version_sum!=3*repetitions)
    result={"repetitions_per_case":repetitions,**counts,"false_accepts":false_accepts,"false_rejects":false_rejects,
            "semantic_violations":false_accepts,"business_invariant_violations":invariant_violations}
    RESULTS.mkdir(exist_ok=True); path=RESULTS/"tatp_semantic_disturbance.json"; path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2)); print(path)
    if false_accepts or false_rejects or invariant_violations: raise RuntimeError("TATP semantic disturbance test failed")
    return result
def main():
    p=argparse.ArgumentParser(); p.add_argument("--repetitions",type=int,default=100); a=p.parse_args(); run(a.repetitions)
if __name__=="__main__": main()
