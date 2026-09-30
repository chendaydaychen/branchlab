"""Transaction-aware wrapper for the upstream tau3 Environment.

The wrapper intentionally lives outside the upstream checkout.  It preserves
the original tool schemas and responses while adding strict OCC validation,
task-semantic validation, and a task-scoped shared read cache.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from typing import Any, Literal

from tau2.data_model.message import AssistantMessage, ToolCall, ToolMessage
from tau2.environment.environment import Environment

from branchlab.semantic_contracts import (
    CompiledContract,
    ContractError,
    SemanticContract,
    compile_contract,
)


Mode = Literal["2pl", "occ", "branchlab"]


def _canonical(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _call_key(name: str, arguments: dict[str, Any]) -> str:
    return f"{name}:{_canonical(arguments)}"


@dataclass
class TxMetrics:
    tool_calls: int = 0
    read_calls: int = 0
    write_calls: int = 0
    physical_reads: int = 0
    shared_read_hits: int = 0
    validations: int = 0
    validation_failures: int = 0
    semantic_rebases: int = 0
    cache_invalidations: int = 0
    disturbances_applied: int = 0
    disturbances_blocked: int = 0
    contract_checks: int = 0
    contract_rejections: int = 0
    contract_compilations: int = 0


@dataclass(frozen=True)
class ReadObservation:
    name: str
    arguments_json: str
    content: str

    @property
    def arguments(self) -> dict[str, Any]:
        return json.loads(self.arguments_json)


class SharedReadCache:
    """Thread-safe cache shared by speculative branches of the same task."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, str], str] = {}

    def get(self, namespace: str, key: str) -> str | None:
        with self._lock:
            return self._entries.get((namespace, key))

    def put(self, namespace: str, key: str, content: str) -> None:
        with self._lock:
            self._entries[(namespace, key)] = content

    def invalidate_namespace(self, namespace: str) -> int:
        with self._lock:
            keys = [key for key in self._entries if key[0] == namespace]
            for key in keys:
                del self._entries[key]
            return len(keys)


class TransactionalEnvironment:
    """Drop-in Environment facade for 2PL, strict OCC, and BranchLab.

    Validation happens immediately before every write.  This keeps the live
    tau3 interaction protocol unchanged: the agent still receives the exact
    upstream tool response or a normal tool error on a validation conflict.
    """

    def __init__(
        self,
        inner: Environment,
        mode: Mode,
        *,
        shared_cache: SharedReadCache | None = None,
        branch_id: str = "default",
        semantic_contract: SemanticContract | None = None,
    ) -> None:
        if mode not in {"2pl", "occ", "branchlab"}:
            raise ValueError(f"unsupported transaction mode: {mode}")
        self.inner = inner
        self.mode = mode
        self.shared_cache = shared_cache or SharedReadCache()
        self.metrics = TxMetrics()
        self._observations: dict[str, ReadObservation] = {}
        self._mutex = threading.RLock()
        self._namespace = "uninitialized"
        self._branch_id = branch_id
        self._compiled_contract: CompiledContract | None = None
        self._contract_template = semantic_contract

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    @property
    def tools(self):
        return self.inner.tools

    @property
    def user_tools(self):
        return self.inner.user_tools

    @property
    def solo_mode(self):
        return self.inner.solo_mode

    def set_state(self, *args, **kwargs) -> None:
        self.inner.set_state(*args, **kwargs)
        self._observations.clear()
        self._namespace = self.inner.get_db_hash() or "no-db"
        message_history = kwargs.get("message_history")
        if message_history is None and len(args) >= 3:
            message_history = args[2]
        if message_history:
            self._restore_observations(message_history)

    @property
    def snapshot_id(self) -> str:
        return self._namespace

    def install_compiled_contract(self, contract: CompiledContract) -> None:
        """Install a contract already bound to this branch, snapshot, and write."""
        self._compiled_contract = contract

    def _restore_observations(self, message_history) -> None:
        """Rebuild a forked branch's read set from its shared prefix."""
        pending: dict[str, ToolCall] = {}
        for message in message_history:
            if isinstance(message, AssistantMessage):
                for call in message.tool_calls or []:
                    if not self._is_write(call.name):
                        pending[call.id] = call
            elif isinstance(message, ToolMessage):
                call = pending.pop(message.id, None)
                if call is not None and not message.error:
                    self._record_read(call, message.content)

    def get_tools(self):
        return self.inner.get_tools()

    def get_user_tools(self, include=None):
        return self.inner.get_user_tools(include=include)

    def get_policy(self) -> str:
        return self.inner.get_policy()

    def get_domain_name(self) -> str:
        return self.inner.get_domain_name()

    def get_info(self, include_tool_info: bool = False):
        return self.inner.get_info(include_tool_info=include_tool_info)

    def get_db_hash(self):
        return self.inner.get_db_hash()

    def metrics_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, **asdict(self.metrics)}

    def inject_benign_disturbance(self) -> tuple[bool, str]:
        """Change an observed value that is irrelevant to the next write.

        The method is used by the paired trace-replay experiment.  Under 2PL
        the concurrent change is modeled as blocked by the held lock.  OCC and
        BranchLab receive exactly the same state change.
        """
        if self.mode == "2pl":
            self.metrics.disturbances_blocked += 1
            return True, "blocked-by-2pl"

        observations = list(self._observations.values())
        # Prefer reservations: total_baggages is independent of passenger,
        # flight, and cancellation predicates in the upstream implementation.
        for observation in observations:
            if observation.name != "get_reservation_details":
                continue
            reservation_id = observation.arguments["reservation_id"]
            reservation = self._reservation(reservation_id)
            if reservation is not None:
                reservation.total_baggages += 1
                self.metrics.disturbances_applied += 1
                return True, f"reservation:{reservation_id}:total_baggages"

        # User address is independent of booking/update payment validity.
        for observation in observations:
            if observation.name != "get_user_details":
                continue
            user_id = observation.arguments["user_id"]
            user = self._user(user_id)
            if user is not None:
                user.address.city = f"{user.address.city} (updated)"
                self.metrics.disturbances_applied += 1
                return True, f"user:{user_id}:address.city"

        # A price decrease is a safe rebase for a previously selected flight.
        for observation in observations:
            if observation.name not in {"search_direct_flight", "search_onestop_flight"}:
                continue
            try:
                payload = json.loads(observation.content)
            except json.JSONDecodeError:
                continue
            stack = list(payload) if isinstance(payload, list) else [payload]
            while stack:
                item = stack.pop(0)
                if isinstance(item, list):
                    stack.extend(item)
                    continue
                if not isinstance(item, dict) or "flight_number" not in item:
                    continue
                number = item["flight_number"]
                date = observation.arguments.get("date") or item.get("date")
                flight = self.inner.tools.db.flights.get(number)
                if flight is None or date not in flight.dates:
                    continue
                instance = flight.dates[date]
                prices = getattr(instance, "prices", None)
                if not prices:
                    continue
                cabin = sorted(prices)[0]
                prices[cabin] = max(0, prices[cabin] - 1)
                self.metrics.disturbances_applied += 1
                return True, f"flight:{number}/{date}:{cabin}:price-decrease"
        return False, "no-observed-mutable-resource"

    def inject_harmful_disturbance(self, call: ToolCall) -> tuple[bool, str]:
        """Invalidate a hard predicate of the pending write."""
        if self.mode == "2pl":
            self.metrics.disturbances_blocked += 1
            return True, "blocked-by-2pl"

        args = call.arguments
        if "reservation_id" in args:
            reservation = self._reservation(args["reservation_id"])
            if reservation is not None:
                reservation.status = "cancelled"
                self.metrics.disturbances_applied += 1
                return True, f"reservation:{args['reservation_id']}:cancelled"

        if call.name == "book_reservation":
            user = self._user(args["user_id"])
            if user is not None and args.get("payment_methods"):
                payment = args["payment_methods"][0]
                payment_id = (
                    payment.get("payment_id")
                    if isinstance(payment, dict)
                    else payment.payment_id
                )
                if payment_id in user.payment_methods:
                    del user.payment_methods[payment_id]
                    self.metrics.disturbances_applied += 1
                    return True, f"user:{args['user_id']}:payment-removed:{payment_id}"

        if call.name == "send_certificate":
            user_id = args["user_id"]
            if user_id in self.inner.tools.db.users:
                del self.inner.tools.db.users[user_id]
                self.metrics.disturbances_applied += 1
                return True, f"user:{user_id}:removed"
        return False, "no-hard-predicate-target"

    def _is_write(self, name: str) -> bool:
        return self.inner._is_mutating_tool(name)

    def _record_read(self, call: ToolCall, content: str) -> None:
        key = _call_key(call.name, call.arguments)
        self._observations[key] = ReadObservation(
            name=call.name,
            arguments_json=_canonical(call.arguments),
            content=content,
        )

    def _fresh_read(self, observation: ReadObservation) -> str:
        result = self.inner.make_tool_call(
            observation.name,
            requestor="assistant",
            **observation.arguments,
        )
        return self.inner.to_json_str(result)

    def _strict_validate(self) -> tuple[bool, str]:
        for observation in self._observations.values():
            try:
                current = self._fresh_read(observation)
            except Exception as error:
                return False, f"read dependency failed: {observation.name}: {error}"
            if current != observation.content:
                return False, f"read dependency changed: {observation.name}"
        return True, "strict-read-set-valid"

    def _reservation(self, reservation_id: str):
        db = self.inner.tools.db
        return db.reservations.get(reservation_id)

    def _user(self, user_id: str):
        db = self.inner.tools.db
        return db.users.get(user_id)

    def _observed_json(self, name: str, **arguments: Any) -> Any | None:
        observation = self._observations.get(_call_key(name, arguments))
        if observation is None:
            return None
        try:
            return json.loads(observation.content)
        except json.JSONDecodeError:
            return observation.content

    def _validate_selected_flights(
        self,
        flights: list[dict[str, Any]],
        cabin: str,
        passengers: int,
    ) -> tuple[bool, str]:
        db = self.inner.tools.db
        for selected in flights:
            number = selected["flight_number"]
            date = selected["date"]
            flight = db.flights.get(number)
            if flight is None or date not in flight.dates:
                return False, f"selected flight disappeared: {number}/{date}"
            instance = flight.dates[date]
            if getattr(instance, "status", None) != "available":
                return False, f"selected flight unavailable: {number}/{date}"
            seats = getattr(instance, "available_seats", {})
            if seats.get(cabin, 0) < passengers:
                return False, f"insufficient seats: {number}/{date}/{cabin}"

            # A lower current price is a safe semantic rebase.  A price increase
            # invalidates the user's previously confirmed amount.
            observed_price = None
            for observation in self._observations.values():
                if observation.name not in {"search_direct_flight", "search_onestop_flight"}:
                    continue
                try:
                    payload = json.loads(observation.content)
                except json.JSONDecodeError:
                    continue
                stack = list(payload) if isinstance(payload, list) else [payload]
                while stack:
                    item = stack.pop()
                    if isinstance(item, list):
                        stack.extend(item)
                    elif isinstance(item, dict) and item.get("flight_number") == number:
                        item_date = item.get("date") or observation.arguments.get("date")
                        if item_date != date:
                            continue
                        prices = item.get("prices") or {}
                        if cabin in prices:
                            observed_price = prices[cabin]
                            break
                if observed_price is not None:
                    break
            current_price = getattr(instance, "prices", {}).get(cabin)
            if observed_price is not None and current_price is not None:
                if current_price > observed_price:
                    return False, f"confirmed price increased: {number}/{date}/{cabin}"
        return True, "selected-flights-valid"

    def _semantic_validate(self, call: ToolCall) -> tuple[bool, str]:
        args = call.arguments
        name = call.name

        if name == "cancel_reservation":
            reservation = self._reservation(args["reservation_id"])
            if reservation is None or reservation.status == "cancelled":
                return False, "reservation missing or already cancelled"
            observed = self._observed_json(
                "get_reservation_details", reservation_id=args["reservation_id"]
            )
            if observed is not None:
                if observed.get("user_id") != reservation.user_id:
                    return False, "reservation owner changed"
                if observed.get("payment_history") != [
                    payment.model_dump() for payment in reservation.payment_history
                ]:
                    return False, "refund basis changed"
            return True, "cancel predicates valid"

        if name in {
            "update_reservation_baggages",
            "update_reservation_flights",
            "update_reservation_passengers",
        }:
            reservation = self._reservation(args["reservation_id"])
            if reservation is None or reservation.status == "cancelled":
                return False, "reservation missing or cancelled"
            observed = self._observed_json(
                "get_reservation_details", reservation_id=args["reservation_id"]
            )
            if observed is not None and observed.get("user_id") != reservation.user_id:
                return False, "reservation owner changed"

            if name == "update_reservation_passengers":
                if len(args["passengers"]) != len(reservation.passengers):
                    return False, "passenger cardinality changed"
                return True, "passenger predicates valid"

            user = self._user(reservation.user_id)
            payment_id = args["payment_id"]
            if user is None or payment_id not in user.payment_methods:
                return False, "payment method disappeared"

            if name == "update_reservation_baggages":
                if observed is not None and observed.get("nonfree_baggages") != reservation.nonfree_baggages:
                    return False, "baggage price basis changed"
                return True, "baggage predicates valid"

            if observed is not None:
                old_flights = [
                    {key: item.get(key) for key in ("flight_number", "date", "price")}
                    for item in observed.get("flights", [])
                ]
                current_flights = [
                    {key: getattr(item, key) for key in ("flight_number", "date", "price")}
                    for item in reservation.flights
                ]
                if old_flights != current_flights or len(observed.get("passengers", [])) != len(reservation.passengers):
                    return False, "flight price basis or passenger count changed"
            return self._validate_selected_flights(
                args["flights"], args["cabin"], len(reservation.passengers)
            )

        if name == "book_reservation":
            user = self._user(args["user_id"])
            if user is None:
                return False, "user disappeared"
            for payment in args["payment_methods"]:
                payment_id = payment.get("payment_id") if isinstance(payment, dict) else payment.payment_id
                if payment_id not in user.payment_methods:
                    return False, f"payment method disappeared: {payment_id}"
            return self._validate_selected_flights(
                args["flights"], args["cabin"], len(args["passengers"])
            )

        if name == "send_certificate":
            return (self._user(args["user_id"]) is not None, "certificate recipient valid")

        # Safe fallback: unknown mutations receive strict OCC validation.
        return self._strict_validate()

    def _validate(self, call: ToolCall) -> tuple[bool, str]:
        self.metrics.validations += 1
        if self.mode == "occ":
            return self._strict_validate()
        if self.mode == "branchlab":
            if self._compiled_contract is None and self._contract_template is not None:
                try:
                    self._compiled_contract = compile_contract(
                        self._contract_template,
                        branch_id=self._branch_id,
                        snapshot_id=self._namespace,
                        operation=call.name,
                        arguments=call.arguments,
                    )
                    self.metrics.contract_compilations += 1
                except ContractError as error:
                    self.metrics.contract_rejections += 1
                    return False, f"contract-compilation-failed: {error}"
            if self._compiled_contract is not None:
                self.metrics.contract_checks += 1
                authorized, contract_reason = self._compiled_contract.authorizes(
                    branch_id=self._branch_id,
                    snapshot_id=self._namespace,
                    operation=call.name,
                    arguments=call.arguments,
                )
                if not authorized:
                    self.metrics.contract_rejections += 1
                    return False, contract_reason
            valid, reason = self._semantic_validate(call)
            if valid and self._observations:
                self.metrics.semantic_rebases += 1
            return valid, reason
        return True, "2pl-lock-protected"

    def _refresh_observations(self) -> None:
        refreshed = {}
        for key, observation in self._observations.items():
            try:
                content = self._fresh_read(observation)
            except Exception:
                continue
            refreshed[key] = ReadObservation(
                observation.name, observation.arguments_json, content
            )
        self._observations = refreshed

    def get_response(self, call: ToolCall) -> ToolMessage:
        self.metrics.tool_calls += 1
        is_write = self._is_write(call.name)
        if is_write:
            self.metrics.write_calls += 1
        else:
            self.metrics.read_calls += 1

        with self._mutex:
            if not is_write and self.mode == "branchlab":
                key = _call_key(call.name, call.arguments)
                cached = self.shared_cache.get(self._namespace, key)
                if cached is not None:
                    self.metrics.shared_read_hits += 1
                    self._record_read(call, cached)
                    return ToolMessage(
                        id=call.id,
                        content=cached,
                        requestor=call.requestor,
                        role="tool",
                        error=False,
                    )

            if is_write:
                valid, reason = self._validate(call)
                if not valid:
                    self.metrics.validation_failures += 1
                    return ToolMessage(
                        id=call.id,
                        content=f"Error: TransactionConflict: {reason}",
                        requestor=call.requestor,
                        role="tool",
                        error=True,
                    )

            response = self.inner.get_response(call)
            if not is_write:
                self.metrics.physical_reads += 1
                if not response.error:
                    self._record_read(call, response.content)
                    if self.mode == "branchlab":
                        self.shared_cache.put(
                            self._namespace,
                            _call_key(call.name, call.arguments),
                            response.content,
                        )
            elif not response.error:
                # Detach this branch from the immutable base snapshot.  Do not
                # delete the old namespace: sibling speculative branches may
                # still safely reuse its prefix reads.
                self.metrics.cache_invalidations += 1
                self._namespace = self.inner.get_db_hash() or self._namespace
                self._refresh_observations()
            return response
