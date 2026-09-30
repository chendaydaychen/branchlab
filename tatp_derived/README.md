# TATP-derived speculative transaction workload

This is **not an official BenchBase/TATP score**.  It preserves the publicly
available TATP PostgreSQL entity model and the semantics of the common reads
(`GetSubscriberData`, `GetAccessData`) followed by `UpdateLocation`.  BranchLab
adds `row_version` for application-level OCC validation and `branch_commit` for
auditing speculative branch commits.

For every logical task, several candidate branches read the same subscriber and
access-info record, perform equal simulated discovery/decision time, then issue
an `UpdateLocation`-style update of `subscriber.vlr_location`.  The selected
subscriber is sampled from a configurable hot set, making conflict intensity
explicit and reproducible.

Modes:

- `2pl`: PostgreSQL row locks are acquired before discovery and held through
  decision and commit.
- `occ`: every branch reads versions without locks, then validates both common
  records and applies a compare-and-swap update at commit; retries are counted.
- `reuse`: same OCC protocol, but a task-local common-read result is computed
  once, shared by sibling branches, and still version-validated at each commit.

Run from WSL after starting the project PostgreSQL service:

```bash
source .venv-wsl/bin/activate
python -m branchlab.tatp_runner setup --subscribers 100
python -m branchlab.tatp_runner run --mode reuse --workers 8 --tasks 40 --candidates 4 --hot-subscribers 1 --seed 1
```

The source schema and procedure names were checked against BenchBase's TATP
PostgreSQL DDL and procedure implementation, vendored under `vendor/benchbase`.
