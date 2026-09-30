"""Task-semantic contract for speculative Agent transactions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Protocol

@dataclass(frozen=True)
class Validation:
    acceptable: bool
    rebased_version: int | None
    reason: str

class TaskSemantic(Protocol):
    """Declares hard predicates, tolerated changes, and a safe rebase result."""
    name: str
    def validate(self, observed: Mapping[str, object], current: Mapping[str, object]) -> Validation: ...

@dataclass(frozen=True)
class SeatReservationSemantic:
    budget: float = 120.0
    name: str = "seat-reservation-within-budget"
    def validate(self, observed, current) -> Validation:
        if int(current["seats_left"]) <= 0:
            return Validation(False, None, "no-seat-remains")
        if float(current["price"]) > self.budget:
            return Validation(False, None, "budget-violated")
        return Validation(True, int(current["row_version"]), "semantic-rebase")

@dataclass(frozen=True)
class SubscriberLocationSemantic:
    """Location is last-writer-wins; subscriber identity/access must survive."""
    name: str = "subscriber-location-update"
    def validate(self, observed, current) -> Validation:
        if not bool(current["subscriber_exists"]) or not bool(current["access_exists"]):
            return Validation(False, None, "subscriber-or-access-missing")
        return Validation(True, int(current["row_version"]), "location-rebase")
