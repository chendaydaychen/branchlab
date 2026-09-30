from copy import deepcopy

from tau2.data_model.message import AssistantMessage, ToolCall
from tau2.domains.airline.data_model import FlightDB
from tau2.domains.airline.environment import get_environment

from branchlab.tau3_tx_environment import SharedReadCache, TransactionalEnvironment
from branchlab.semantic_contracts import SemanticContract, compile_contract


DB_DATA = {
    "flights": {
        "HAT001": {
            "flight_number": "HAT001",
            "origin": "PHL",
            "destination": "LGA",
            "scheduled_departure_time_est": "06:00:00",
            "scheduled_arrival_time_est": "07:00:00",
            "dates": {
                "2024-05-16": {
                    "status": "available",
                    "available_seats": {
                        "basic_economy": 16,
                        "economy": 10,
                        "business": 13,
                    },
                    "prices": {
                        "basic_economy": 87,
                        "economy": 122,
                        "business": 471,
                    },
                }
            },
        }
    },
    "users": {
        "mia_li_3668": {
            "user_id": "mia_li_3668",
            "name": {"first_name": "Mia", "last_name": "Li"},
            "address": {
                "address1": "975 Sunset Drive",
                "address2": "Suite 217",
                "city": "Austin",
                "country": "USA",
                "state": "TX",
                "zip": "78750",
            },
            "email": "mia@example.com",
            "dob": "1990-04-05",
            "payment_methods": {
                "credit_card_4421486": {
                    "source": "credit_card",
                    "brand": "visa",
                    "last_four": "7447",
                    "id": "credit_card_4421486",
                }
            },
            "saved_passengers": [],
            "membership": "gold",
            "reservations": ["4WQ150"],
        }
    },
    "reservations": {
        "4WQ150": {
            "reservation_id": "4WQ150",
            "user_id": "mia_li_3668",
            "origin": "PHL",
            "destination": "LGA",
            "flight_type": "one_way",
            "cabin": "economy",
            "flights": [
                {
                    "origin": "PHL",
                    "destination": "LGA",
                    "flight_number": "HAT001",
                    "date": "2024-05-16",
                    "price": 122,
                }
            ],
            "passengers": [
                {"first_name": "Chen", "last_name": "Jackson", "dob": "1956-07-07"},
                {"first_name": "Raj", "last_name": "Smith", "dob": "1967-04-01"},
            ],
            "payment_history": [{"payment_id": "credit_card_4421486", "amount": 500}],
            "created_at": "2024-05-02T03:10:19",
            "total_baggages": 5,
            "nonfree_baggages": 0,
            "insurance": "no",
        }
    },
}


def make_tx(mode, cache=None):
    db = FlightDB.model_validate(deepcopy(DB_DATA))
    tx = TransactionalEnvironment(get_environment(db), mode, shared_cache=cache)
    tx.set_state(None, None, [])
    return tx


def passenger_contract():
    return SemanticContract.from_dict(
        {
            "version": "branchlab.contract.v1",
            "task_id": "test",
            "operation": "update_reservation_passengers",
            "authorization": ["authenticated_user", "explicit_user_confirmation"],
            "hard_predicates": [
                "reservation_exists",
                "reservation_owned_by_user",
                "reservation_active",
                "passenger_count_unchanged",
            ],
            "semantic_dependencies": [
                "reservation.user_id",
                "reservation.status",
                "reservation.passengers.count",
            ],
            "tolerated_changes": ["unrelated_field_change"],
            "write_effects": ["reservation.passengers := confirmed_passenger_records"],
            "source_evidence": ["test user confirmed the passenger update"],
        }
    )


def call(call_id, name, **arguments):
    return ToolCall(id=call_id, name=name, arguments=arguments, requestor="assistant")


def test_shared_read_cache_reuses_across_candidate_environments():
    cache = SharedReadCache()
    first = make_tx("branchlab", cache)
    second = make_tx("branchlab", cache)
    request = call("r1", "get_reservation_details", reservation_id="4WQ150")

    one = first.get_response(request)
    two = second.get_response(call("r2", "get_reservation_details", reservation_id="4WQ150"))

    assert not one.error and not two.error
    assert one.content == two.content
    assert first.metrics.physical_reads == 1
    assert second.metrics.physical_reads == 0
    assert second.metrics.shared_read_hits == 1


def test_fork_restores_read_observations_from_prefix_history():
    prefix_tx = make_tx("branchlab")
    read = call("r1", "get_reservation_details", reservation_id="4WQ150")
    result = prefix_tx.get_response(read)
    prefix = [
        AssistantMessage(role="assistant", tool_calls=[read]),
        result,
    ]

    db = FlightDB.model_validate(deepcopy(DB_DATA))
    branch = TransactionalEnvironment(get_environment(db), "branchlab")
    branch.set_state(None, None, prefix)
    branch.inner.tools.db.reservations["4WQ150"].passengers.pop()
    response = branch.get_response(
        call(
            "w1",
            "update_reservation_passengers",
            reservation_id="4WQ150",
            passengers=deepcopy(DB_DATA["reservations"]["4WQ150"]["passengers"]),
        )
    )

    assert response.error
    assert "passenger cardinality changed" in response.content


def test_branch_write_does_not_evict_sibling_prefix_cache():
    cache = SharedReadCache()
    writer = make_tx("branchlab", cache)
    sibling = make_tx("branchlab", cache)
    writer.get_response(call("r1", "get_reservation_details", reservation_id="4WQ150"))
    writer.get_response(
        call(
            "w1",
            "update_reservation_passengers",
            reservation_id="4WQ150",
            passengers=deepcopy(DB_DATA["reservations"]["4WQ150"]["passengers"]),
        )
    )
    response = sibling.get_response(
        call("r2", "get_reservation_details", reservation_id="4WQ150")
    )
    assert not response.error
    assert sibling.metrics.shared_read_hits == 1
    assert sibling.metrics.physical_reads == 0


def test_occ_rejects_benign_change_that_semantic_validation_accepts():
    passengers = deepcopy(DB_DATA["reservations"]["4WQ150"]["passengers"])
    for mode, expected_error in (("occ", True), ("branchlab", False)):
        tx = make_tx(mode)
        tx.get_response(call("r", "get_reservation_details", reservation_id="4WQ150"))
        tx.inner.tools.db.reservations["4WQ150"].total_baggages += 1
        result = tx.get_response(
            call(
                "w",
                "update_reservation_passengers",
                reservation_id="4WQ150",
                passengers=passengers,
            )
        )
        assert result.error is expected_error


def test_branchlab_rejects_harmful_passenger_cardinality_change():
    tx = make_tx("branchlab")
    tx.get_response(call("r", "get_reservation_details", reservation_id="4WQ150"))
    tx.inner.tools.db.reservations["4WQ150"].passengers.pop()
    result = tx.get_response(
        call(
            "w",
            "update_reservation_passengers",
            reservation_id="4WQ150",
            passengers=deepcopy(DB_DATA["reservations"]["4WQ150"]["passengers"]),
        )
    )
    assert result.error
    assert "passenger cardinality changed" in result.content


def test_compiled_contract_gate_rejects_changed_write_intent():
    tx = make_tx("branchlab")
    original_arguments = {
        "reservation_id": "4WQ150",
        "passengers": deepcopy(DB_DATA["reservations"]["4WQ150"]["passengers"]),
    }
    compiled = compile_contract(
        passenger_contract(),
        branch_id="default",
        snapshot_id=tx.snapshot_id,
        operation="update_reservation_passengers",
        arguments=original_arguments,
    )
    tx.install_compiled_contract(compiled)
    changed = deepcopy(original_arguments)
    changed["passengers"][0]["last_name"] = "ChangedAfterContract"
    result = tx.get_response(call("w", "update_reservation_passengers", **changed))
    assert result.error
    assert "contract-write-intent-mismatch" in result.content
    assert tx.metrics.contract_checks == 1
    assert tx.metrics.contract_rejections == 1


def test_saved_contract_template_auto_compiles_on_first_write():
    db = FlightDB.model_validate(deepcopy(DB_DATA))
    tx = TransactionalEnvironment(
        get_environment(db),
        "branchlab",
        branch_id="candidate-1",
        semantic_contract=passenger_contract(),
    )
    tx.set_state(None, None, [])
    result = tx.get_response(
        call(
            "w",
            "update_reservation_passengers",
            reservation_id="4WQ150",
            passengers=deepcopy(DB_DATA["reservations"]["4WQ150"]["passengers"]),
        )
    )
    assert not result.error
    assert tx.metrics.contract_compilations == 1
    assert tx.metrics.contract_checks == 1
    assert tx.metrics.contract_rejections == 0


def test_branchlab_rejects_harmful_disturbance_helper():
    tx = make_tx("branchlab")
    tx.get_response(call("r", "get_reservation_details", reservation_id="4WQ150"))
    write = call(
        "w",
        "update_reservation_passengers",
        reservation_id="4WQ150",
        passengers=deepcopy(DB_DATA["reservations"]["4WQ150"]["passengers"]),
    )
    applied, _ = tx.inject_harmful_disturbance(write)
    assert applied
    result = tx.get_response(write)
    assert result.error
    assert "reservation missing or cancelled" in result.content


def test_branchlab_allows_price_decrease_and_rejects_increase():
    for current_price, expected_error in ((120, False), (130, True)):
        tx = make_tx("branchlab")
        tx.get_response(
            call(
                "r",
                "search_direct_flight",
                origin="PHL",
                destination="LGA",
                date="2024-05-16",
            )
        )
        tx.get_response(call("r2", "get_reservation_details", reservation_id="4WQ150"))
        tx.inner.tools.db.flights["HAT001"].dates["2024-05-16"].prices["economy"] = current_price
        result = tx.get_response(
            call(
                "w",
                "update_reservation_flights",
                reservation_id="4WQ150",
                cabin="economy",
                flights=[{"flight_number": "HAT001", "date": "2024-05-16"}],
                payment_id="credit_card_4421486",
            )
        )
        assert result.error is expected_error


def test_price_validation_distinguishes_same_flight_on_different_dates():
    data = deepcopy(DB_DATA)
    data["flights"]["HAT001"]["dates"]["2024-05-17"] = deepcopy(
        data["flights"]["HAT001"]["dates"]["2024-05-16"]
    )
    data["flights"]["HAT001"]["dates"]["2024-05-17"]["prices"]["economy"] = 80
    tx = TransactionalEnvironment(
        get_environment(FlightDB.model_validate(data)), "branchlab"
    )
    tx.set_state(None, None, [])
    tx.get_response(
        call(
            "other-date",
            "search_direct_flight",
            origin="PHL",
            destination="LGA",
            date="2024-05-17",
        )
    )
    tx.get_response(
        call(
            "selected-date",
            "search_direct_flight",
            origin="PHL",
            destination="LGA",
            date="2024-05-16",
        )
    )
    tx.get_response(call("reservation", "get_reservation_details", reservation_id="4WQ150"))
    result = tx.get_response(
        call(
            "write",
            "update_reservation_flights",
            reservation_id="4WQ150",
            cabin="economy",
            flights=[{"flight_number": "HAT001", "date": "2024-05-16"}],
            payment_id="credit_card_4421486",
        )
    )
    assert not result.error
