# BranchLab: multi-candidate transaction experiment

This is a reproducible first-stage experiment for the research question: how do
concurrency-control policies behave when one user task expands into many
partially overlapping transactional candidates?

## Design

The foundation is PostgreSQL 16, run by Docker in WSL.  The first workload is a
controlled flight rebooking task.  Each logical task creates several candidate
branches that share the user/order/flight discovery phase and then execute a
private action (`rebook`, `cancel_rebook`, or `split`).  The harness can inject
hot inventory rows so that overlapping candidates contend predictably.

The initial baselines are deliberately limited to:

* **2PL**: `SELECT ... FOR UPDATE` locks every row in the candidate read/write
  set and holds the locks until commit.
* **OCC**: candidates read versioned rows without locks, then validate every
  recorded version at commit.  A failed validation aborts and retries the whole
  candidate.
* **Reuse-OCC (our design)**: a task-scoped future shares the common user
  eligibility/discovery computation across its candidates.  The cached user
  version is locked and checked again during every candidate's commit phase;
  an invalid entry is retried through the normal OCC path.

This makes the comparison interpretable: 2PL pays in blocking time; OCC pays in
abort/retry work.  The later research system will use this exact workload and
add a third mode, dependency-safe cross-branch reuse.

## Workload knobs

`--workers` is the number of concurrent logical user tasks, and `--candidates`
is the number of branches per task.  `--hot-flights` controls contention: fewer
hot flights means more candidates read and update the same inventory records.
`--think-ms` keeps locks/read snapshots alive long enough to expose contention.

The experiment has two phases:

1. **Microbenchmark / contention sweep**: candidates=1, 2, 4, 8, 16; workers=1,
   4, 8, 16; hot-flights=1, 2, 8, 32.
2. **Candidate scaling**: fix workers at the throughput knee from phase 1, then
   measure the cost of progressively larger candidate sets.

For every setting, run at least five seeds, retain raw JSON, and report median
plus 5th/95th percentiles.  Use the same seeds and dataset reset for 2PL and
OCC.

## Quick start (from WSL)

```bash
cd /mnt/z/at/branchlab
docker compose up -d
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m branchlab.runner setup
python -m branchlab.runner run --mode 2pl --workers 4 --candidates 4 --tasks 80 --hot-flights 2 --think-ms 8 --seed 1
python -m branchlab.runner run --mode occ --workers 4 --candidates 4 --tasks 80 --hot-flights 2 --think-ms 8 --seed 1
python -m branchlab.runner run --mode reuse --workers 4 --candidates 4 --tasks 80 --hot-flights 2 --discovery-ms 30 --think-ms 8 --seed 1
```

Raw result files are written to `results/`.  `run` checks transaction invariants
after each execution: inventory must never become negative and every order must
have one of the defined states.

## Interpretation guardrails

This is not a claim that PostgreSQL's implementation is generally faster or
slower than another DBMS.  Both modes use the same database, schema, driver,
candidate generator and fault-free workload.  The measured difference isolates
the policy trade-off under speculative candidate execution.

The 2PL implementation has an intentionally stable row-lock order to avoid
turning deadlocks into a confounder.  The OCC implementation uses optimistic
read-set validation, so its retry rate is part of the reported result rather
than a harness error.
