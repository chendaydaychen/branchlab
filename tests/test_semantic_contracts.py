import json
from pathlib import Path

import pytest

from branchlab.semantic_contracts import (
    ContractError,
    SemanticContract,
    compare_contract,
    compile_contract,
    harden_contract,
    safety_gaps,
)


ROOT = Path(__file__).resolve().parents[1]


def cases():
    return json.loads((ROOT / "experiments" / "semantic_contract_canary.json").read_text())


def test_gold_contracts_are_schema_valid():
    for case in cases():
        contract = SemanticContract.from_dict(case["gold_contract"])
        assert contract.task_id == case["task_id"]
        assert contract.operation == case["operation"]
        assert not any(safety_gaps(contract).values())


def test_unknown_predicate_is_rejected():
    value = cases()[0]["gold_contract"] | {"hard_predicates": ["invented_permission"]}
    with pytest.raises(ContractError, match="unknown identifiers"):
        SemanticContract.from_dict(value)


def test_dangerous_omission_is_reported():
    expected = SemanticContract.from_dict(cases()[2]["gold_contract"])
    value = expected.to_dict()
    value["hard_predicates"].remove("passenger_count_unchanged")
    actual = SemanticContract.from_dict(value)
    metrics = compare_contract(expected, actual)
    assert metrics["dangerous_omissions"] == ["passenger_count_unchanged"]
    assert metrics["hard_predicates"]["recall"] < 1.0


def test_static_guard_catches_and_hardens_minimum_predicate():
    expected = SemanticContract.from_dict(cases()[2]["gold_contract"])
    value = expected.to_dict()
    value["hard_predicates"].remove("reservation_active")
    predicted = SemanticContract.from_dict(value)
    assert safety_gaps(predicted)["hard_predicates"] == ["reservation_active"]
    hardened = harden_contract(predicted)
    assert safety_gaps(hardened) == {"authorization": [], "hard_predicates": []}
    assert compare_contract(expected, hardened)["dangerous_omissions"] == []


def test_compiled_contract_is_bound_to_branch_snapshot_and_write():
    semantic = SemanticContract.from_dict(cases()[2]["gold_contract"])
    arguments = {"reservation_id": "R1", "passengers": [{"name": "A"}]}
    compiled = compile_contract(
        semantic,
        branch_id="b0",
        snapshot_id="s0",
        operation=semantic.operation,
        arguments=arguments,
    )
    assert compiled.authorizes(
        branch_id="b0", snapshot_id="s0", operation=semantic.operation, arguments=arguments
    )[0]
    assert not compiled.authorizes(
        branch_id="b1", snapshot_id="s0", operation=semantic.operation, arguments=arguments
    )[0]
    assert not compiled.authorizes(
        branch_id="b0", snapshot_id="s1", operation=semantic.operation, arguments=arguments
    )[0]
    assert not compiled.authorizes(
        branch_id="b0",
        snapshot_id="s0",
        operation=semantic.operation,
        arguments=arguments | {"reservation_id": "R2"},
    )[0]
