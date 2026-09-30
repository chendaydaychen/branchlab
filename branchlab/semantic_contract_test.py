"""Deterministic boundary tests for semantic contracts and workload mapping."""
from types import SimpleNamespace

from branchlab.seats_runner import job
from branchlab.task_semantics import SeatReservationSemantic, SubscriberLocationSemantic

def main():
    seat = SeatReservationSemantic()
    ok = seat.validate({}, {"seats_left": 3, "price": 100, "row_version": 9})
    sold_out = seat.validate({}, {"seats_left": 0, "price": 100, "row_version": 9})
    over_budget = seat.validate({}, {"seats_left": 3, "price": 121, "row_version": 9})
    assert ok.acceptable and ok.rebased_version == 9 and ok.reason == "semantic-rebase"
    assert not sold_out.acceptable and sold_out.reason == "no-seat-remains"
    assert not over_budget.acceptable and over_budget.reason == "budget-violated"
    location = SubscriberLocationSemantic()
    rebased = location.validate({}, {"subscriber_exists": True, "access_exists": True, "row_version": 6})
    missing = location.validate({}, {"subscriber_exists": True, "access_exists": False, "row_version": 6})
    assert rebased.acceptable and rebased.rebased_version == 6
    assert not missing.acceptable and missing.reason == "subscriber-or-access-missing"
    args = SimpleNamespace(hot_flights=1, tasks=120, candidates=4, customers=1000)
    winner_seats = [job(task, 0, args)[5] for task in range(args.tasks)]
    assert len(set(winner_seats)) == args.tasks
    args.hot_flights = 40
    args.tasks = 1000
    per_flight = {}
    for task in range(args.tasks):
        row = job(task, 0, args)
        per_flight.setdefault(row[3], []).append(row[5])
    assert all(len(seats) == len(set(seats)) for seats in per_flight.values())
    print("semantic contract boundaries: PASS")
if __name__ == "__main__":
    main()
