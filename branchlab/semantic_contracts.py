"""Machine-checkable semantic contracts for Agent transaction commits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Iterable


OPERATIONS = frozenset(
    {
        "book_reservation",
        "cancel_reservation",
        "update_reservation_flights",
        "update_reservation_passengers",
        "update_reservation_baggages",
    }
)

AUTHORIZATION_PREDICATES = frozenset(
    {
        "authenticated_user",
        "explicit_user_confirmation",
        "payment_method_owned_by_user",
    }
)

HARD_PREDICATES = frozenset(
    {
        "reservation_exists",
        "reservation_owned_by_user",
        "reservation_active",
        "no_segment_flown",
        "cancellation_policy_eligible",
        "refund_destination_unchanged",
        "passenger_count_unchanged",
        "target_flight_available",
        "seats_sufficient",
        "origin_unchanged",
        "destination_unchanged",
        "trip_type_unchanged",
        "cabin_consistent",
        "payment_method_valid",
        "baggage_not_decreased",
        "insurance_not_added_after_booking",
        "booking_passenger_limit_respected",
        "selected_itinerary_unchanged",
        "quoted_total_within_user_limit",
    }
)

TOLERATED_CHANGES = frozenset(
    {
        "unrelated_field_change",
        "price_decrease_within_user_limit",
        "seat_increase",
        "metadata_only_change",
        "none",
    }
)

MINIMUM_AUTHORIZATION = frozenset(
    {"authenticated_user", "explicit_user_confirmation"}
)

MINIMUM_HARD_PREDICATES = {
    "book_reservation": frozenset(
        {
            "target_flight_available",
            "seats_sufficient",
            "cabin_consistent",
            "payment_method_valid",
            "booking_passenger_limit_respected",
        }
    ),
    "cancel_reservation": frozenset(
        {
            "reservation_exists",
            "reservation_owned_by_user",
            "reservation_active",
            "no_segment_flown",
            "cancellation_policy_eligible",
            "refund_destination_unchanged",
        }
    ),
    "update_reservation_flights": frozenset(
        {
            "reservation_exists",
            "reservation_owned_by_user",
            "reservation_active",
            "origin_unchanged",
            "destination_unchanged",
            "trip_type_unchanged",
            "target_flight_available",
            "seats_sufficient",
            "payment_method_valid",
        }
    ),
    "update_reservation_passengers": frozenset(
        {
            "reservation_exists",
            "reservation_owned_by_user",
            "reservation_active",
            "passenger_count_unchanged",
        }
    ),
    "update_reservation_baggages": frozenset(
        {
            "reservation_exists",
            "reservation_owned_by_user",
            "reservation_active",
            "baggage_not_decreased",
        }
    ),
}


class ContractError(ValueError):
    pass


def _string_set(value: Any, field: str, allowed: frozenset[str] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{field} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"{field} must contain non-empty strings")
    normalized = tuple(dict.fromkeys(item.strip() for item in value))
    if len(normalized) != len(value):
        raise ContractError(f"{field} contains duplicates")
    if allowed is not None:
        unknown = sorted(set(normalized) - allowed)
        if unknown:
            raise ContractError(f"{field} contains unknown identifiers: {unknown}")
    return normalized


@dataclass(frozen=True)
class SemanticContract:
    version: str
    task_id: str
    operation: str
    authorization: tuple[str, ...]
    hard_predicates: tuple[str, ...]
    semantic_dependencies: tuple[str, ...]
    tolerated_changes: tuple[str, ...]
    write_effects: tuple[str, ...]
    source_evidence: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SemanticContract":
        required = {
            "version",
            "task_id",
            "operation",
            "authorization",
            "hard_predicates",
            "semantic_dependencies",
            "tolerated_changes",
            "write_effects",
            "source_evidence",
        }
        if not isinstance(value, dict):
            raise ContractError("contract must be a JSON object")
        missing = sorted(required - value.keys())
        extra = sorted(value.keys() - required)
        if missing or extra:
            raise ContractError(f"schema mismatch: missing={missing}, extra={extra}")
        if value["version"] != "branchlab.contract.v1":
            raise ContractError("unsupported contract version")
        task_id = str(value["task_id"]).strip()
        operation = str(value["operation"]).strip()
        if not task_id:
            raise ContractError("task_id must be non-empty")
        if operation not in OPERATIONS:
            raise ContractError(f"unknown operation: {operation}")
        return cls(
            version=value["version"],
            task_id=task_id,
            operation=operation,
            authorization=_string_set(value["authorization"], "authorization", AUTHORIZATION_PREDICATES),
            hard_predicates=_string_set(value["hard_predicates"], "hard_predicates", HARD_PREDICATES),
            semantic_dependencies=_string_set(value["semantic_dependencies"], "semantic_dependencies"),
            tolerated_changes=_string_set(value["tolerated_changes"], "tolerated_changes", TOLERATED_CHANGES),
            write_effects=_string_set(value["write_effects"], "write_effects"),
            source_evidence=_string_set(value["source_evidence"], "source_evidence"),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for field in (
            "authorization",
            "hard_predicates",
            "semantic_dependencies",
            "tolerated_changes",
            "write_effects",
            "source_evidence",
        ):
            value[field] = list(value[field])
        return value


def canonical_write_intent(operation: str, arguments: dict[str, Any]) -> str:
    if operation not in OPERATIONS:
        raise ContractError(f"unknown operation: {operation}")
    return json.dumps(
        {"operation": operation, "arguments": arguments},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def write_intent_digest(operation: str, arguments: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_write_intent(operation, arguments).encode()).hexdigest()


@dataclass(frozen=True)
class CompiledContract:
    """Trusted runtime envelope around an LLM-proposed semantic contract."""

    semantic: SemanticContract
    branch_id: str
    snapshot_id: str
    write_intent_sha256: str

    def authorizes(
        self,
        *,
        branch_id: str,
        snapshot_id: str,
        operation: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, str]:
        if branch_id != self.branch_id:
            return False, "contract-branch-mismatch"
        if snapshot_id != self.snapshot_id:
            return False, "contract-snapshot-mismatch"
        if operation != self.semantic.operation:
            return False, "contract-operation-mismatch"
        if write_intent_digest(operation, arguments) != self.write_intent_sha256:
            return False, "contract-write-intent-mismatch"
        gaps = safety_gaps(self.semantic)
        if any(gaps.values()):
            return False, "contract-minimum-safety-gap"
        return True, "compiled-contract-authorized"


def compile_contract(
    contract: SemanticContract,
    *,
    branch_id: str,
    snapshot_id: str,
    operation: str,
    arguments: dict[str, Any],
) -> CompiledContract:
    if operation != contract.operation:
        raise ContractError("cannot bind contract to a different operation")
    return CompiledContract(
        semantic=harden_contract(contract),
        branch_id=branch_id,
        snapshot_id=snapshot_id,
        write_intent_sha256=write_intent_digest(operation, arguments),
    )


def set_metrics(expected: Iterable[str], actual: Iterable[str]) -> dict[str, float | int]:
    gold, predicted = set(expected), set(actual)
    true_positive = len(gold & predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(gold) if gold else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": len(predicted - gold),
        "false_negative": len(gold - predicted),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def compare_contract(expected: SemanticContract, actual: SemanticContract) -> dict[str, Any]:
    return {
        "operation_exact": expected.operation == actual.operation,
        "authorization": set_metrics(expected.authorization, actual.authorization),
        "hard_predicates": set_metrics(expected.hard_predicates, actual.hard_predicates),
        "semantic_dependencies": set_metrics(expected.semantic_dependencies, actual.semantic_dependencies),
        "tolerated_changes": set_metrics(expected.tolerated_changes, actual.tolerated_changes),
        "dangerous_omissions": sorted(set(expected.hard_predicates) - set(actual.hard_predicates)),
    }


def safety_gaps(contract: SemanticContract) -> dict[str, list[str]]:
    """Find mandatory operation-level conditions omitted by the LLM."""
    return {
        "authorization": sorted(MINIMUM_AUTHORIZATION - set(contract.authorization)),
        "hard_predicates": sorted(
            MINIMUM_HARD_PREDICATES[contract.operation] - set(contract.hard_predicates)
        ),
    }


def harden_contract(contract: SemanticContract) -> SemanticContract:
    """Add trusted operation-level minima; LLM output may only strengthen them."""
    return SemanticContract(
        version=contract.version,
        task_id=contract.task_id,
        operation=contract.operation,
        authorization=tuple(sorted(set(contract.authorization) | MINIMUM_AUTHORIZATION)),
        hard_predicates=tuple(
            sorted(
                set(contract.hard_predicates)
                | MINIMUM_HARD_PREDICATES[contract.operation]
            )
        ),
        semantic_dependencies=contract.semantic_dependencies,
        tolerated_changes=contract.tolerated_changes,
        write_effects=contract.write_effects,
        source_evidence=contract.source_evidence,
    )
