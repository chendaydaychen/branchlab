# SEATS-derived candidate-reservation workload

This is not an official BenchBase SEATS result. It follows the public SEATS
open-seat discovery and new-reservation data dependencies: candidates read
flight capacity and occupancy, reserve a unique flight-seat and
flight-customer combination, decrement seats left, then record an audit
branch commit.

Each task produces candidate reservations with distinct customers and seats.
They share the same flight availability discovery. Thus reservation inserts are
private, while the legitimate flight-capacity decrement remains a controllable
shared-write conflict. hot_flights controls that contention.

The optional winner-only setting models speculative agent execution: all
candidates validate the shared snapshot, but only the selected candidate
materializes the real reservation. Non-winners emit only a private audit row.

BranchLab's Reuse mode additionally uses task-semantic validation: a changed
flight version is accepted when the invariant relevant to this task still
holds (a seat remains and price is within the 120 budget), then the write is
rebased onto the current locked version. Strict OCC rejects every version
change.

The rule is registered through branchlab.task_semantics.TaskSemantic, whose
contract returns a hard-constraint decision, an optional rebased version, and
an auditable reason. New workloads provide their own semantic implementation.
