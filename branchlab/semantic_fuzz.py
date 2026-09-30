"""Deterministic differential fuzzing for BranchLab semantic contracts.

The oracle functions below are deliberately independent of the production
contract implementation. Random schedules mutate the state observed by a
candidate before its eventual commit validation.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from branchlab.task_semantics import SeatReservationSemantic, SubscriberLocationSemantic

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Counters:
    trials: int = 0
    oracle_accepts: int = 0
    semantic_false_accepts: int = 0
    semantic_false_rejects: int = 0
    strict_false_accepts: int = 0
    strict_false_rejects: int = 0
    rc_false_accepts: int = 0
    rc_false_rejects: int = 0

    def observe(self, oracle: bool, semantic: bool, strict: bool, rc: bool) -> None:
        self.trials += 1
        self.oracle_accepts += int(oracle)
        self.semantic_false_accepts += int(semantic and not oracle)
        self.semantic_false_rejects += int(not semantic and oracle)
        self.strict_false_accepts += int(strict and not oracle)
        self.strict_false_rejects += int(not strict and oracle)
        self.rc_false_accepts += int(rc and not oracle)
        self.rc_false_rejects += int(not rc and oracle)


def seat_oracle(current: dict[str, object], budget: float) -> bool:
    """Independent task specification for a reservable in-budget seat."""
    return int(current["seats_left"]) > 0 and float(current["price"]) <= budget


def subscriber_oracle(current: dict[str, object]) -> bool:
    """Independent task specification for a permitted location update."""
    return bool(current["subscriber_exists"]) and bool(current["access_exists"])


def fuzz_seats(rng: random.Random, trials: int) -> Counters:
    counters = Counters()
    contract = SeatReservationSemantic(budget=120.0)
    for _ in range(trials):
        observed = {
            "seats_left": rng.randint(1, 30),
            "price": rng.randint(80, 120),
            "row_version": rng.randint(0, 1000),
        }
        current = dict(observed)
        for _ in range(rng.randint(0, 12)):
            event = rng.randrange(5)
            if event == 0 and current["seats_left"] > 0:
                current["seats_left"] -= 1
            elif event == 1:
                current["seats_left"] += 1
            elif event == 2:
                current["price"] = rng.randint(80, 160)
            elif event == 3:
                current["price"] = rng.choice((119, 120, 121))
            # event 4 is an irrelevant write that changes only the version.
            current["row_version"] += 1
        oracle = seat_oracle(current, 120.0)
        semantic = contract.validate(observed, current).acceptable
        strict = current["row_version"] == observed["row_version"] and int(current["seats_left"]) > 0
        # The native RC baseline protects capacity atomically but materializes
        # the price observed before the decision delay without rechecking it.
        rc = int(current["seats_left"]) > 0 and float(observed["price"]) <= 120.0
        counters.observe(oracle, semantic, strict, rc)
    return counters


def fuzz_tatp(rng: random.Random, trials: int) -> Counters:
    counters = Counters()
    contract = SubscriberLocationSemantic()
    for _ in range(trials):
        observed = {
            "subscriber_exists": True,
            "access_exists": True,
            "row_version": rng.randint(0, 1000),
        }
        current = dict(observed)
        for _ in range(rng.randint(0, 12)):
            event = rng.randrange(5)
            if event == 0:
                current["row_version"] += 1  # concurrent location update
            elif event == 1:
                current["access_exists"] = False
                current["row_version"] += 1
            elif event == 2:
                current["subscriber_exists"] = False
                current["row_version"] += 1
            elif event == 3 and current["subscriber_exists"]:
                current["access_exists"] = True
                current["row_version"] += 1
            else:
                current["row_version"] += 1
        oracle = subscriber_oracle(current)
        semantic = contract.validate(observed, current).acceptable
        strict = current["row_version"] == observed["row_version"]
        # A read-committed blind write does not encode the original permission
        # dependency and therefore accepts whenever the target row survives.
        rc = bool(current["subscriber_exists"])
        counters.observe(oracle, semantic, strict, rc)
    return counters


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260922)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    result = {
        "seed": args.seed,
        "trials_per_workload": args.trials,
        "seats": asdict(fuzz_seats(rng, args.trials)),
        "tatp": asdict(fuzz_tatp(rng, args.trials)),
    }
    if any(
        result[name][metric]
        for name in ("seats", "tatp")
        for metric in ("semantic_false_accepts", "semantic_false_rejects")
    ):
        raise AssertionError(f"semantic contract diverged from oracle: {result}")
    out = ROOT / "results" / "semantic_differential_fuzz.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    report_lines = [
        "# Semantic differential fuzzing",
        "",
        f"Seed: {args.seed}. Trials per workload: {args.trials}. The oracle is an "
        "independent executable task specification. This is a model-level state/schedule "
        "test; database crash and process-failure injection are evaluated separately.",
        "",
        "| workload | controller | false accepts | false rejects |",
        "|---|---|---:|---:|",
    ]
    for workload in ("seats", "tatp"):
        row = result[workload]
        report_lines.extend(
            [
                f"| {workload} | Semantic validation | {row['semantic_false_accepts']} | {row['semantic_false_rejects']} |",
                f"| {workload} | Strict version validation | {row['strict_false_accepts']} | {row['strict_false_rejects']} |",
                f"| {workload} | RC blind materialization model | {row['rc_false_accepts']} | {row['rc_false_rejects']} |",
            ]
        )
    report = ROOT / "results" / "semantic_differential_fuzz.md"
    report.write_text("\n".join(report_lines) + "\n")
    print(json.dumps(result, indent=2))
    print(out)
    print(report)


if __name__ == "__main__":
    main()
