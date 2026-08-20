"""End-to-end order processing.

Stage order is deliberate: ingest -> reserve -> price -> dispatch.
Pricing runs after reservation because the reservation owns the unit-price
snapshot; a reservation that lapsed and was rebuilt re-captures current
prices, so the quoted total can legally change before dispatch.

Failure semantics:
- FatalError (validation, unknown SKU, insufficient stock): no retry.
  The order fails immediately with a "failed" receipt.
- RetryableError during dispatch: retried with exponential backoff up to
  MAX_DISPATCH_ATTEMPTS, then the order is dead-lettered: the reservation
  is released, the order lands on the dead-letter queue, and the caller
  gets a "dead_lettered" receipt instead of an exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .dispatch import DispatchExhausted, dispatch
from .errors import FatalError
from .ingest import parse_order
from .inventory import Inventory
from .pricing import Quote, price


@dataclass(frozen=True)
class Receipt:
    order_id: str
    status: str  # "dispatched" | "failed" | "dead_lettered"
    carrier: str | None = None
    total_cents: int | None = None
    reason: str | None = None
    attempts: int | None = None


@dataclass
class Pipeline:
    inventory: Inventory
    send: Callable[[str, object], None]
    dead_letters: list[dict] = field(default_factory=list)

    def process(self, raw: dict) -> Receipt:
        try:
            order = parse_order(raw)
        except FatalError as err:
            return Receipt(order_id=str(raw.get("order_id")), status="failed",
                           reason=str(err))

        try:
            reservation = self.inventory.reserve(order)
        except FatalError as err:
            return Receipt(order_id=order.order_id, status="failed", reason=str(err))

        # Always price from the (possibly rebuilt) reservation snapshot.
        quote: Quote = price(reservation)

        try:
            result = dispatch(order, reservation, self.send)
        except DispatchExhausted as err:
            self.inventory.release(order.order_id)
            self.dead_letters.append(
                {"order_id": order.order_id, "reason": str(err.last_error)}
            )
            return Receipt(order_id=order.order_id, status="dead_lettered",
                           reason=str(err.last_error))

        return Receipt(
            order_id=order.order_id,
            status="dispatched",
            carrier=result.carrier,
            total_cents=quote.total_cents,
            attempts=result.attempts,
        )
