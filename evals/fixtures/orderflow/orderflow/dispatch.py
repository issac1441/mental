"""Carrier selection and dispatch with bounded retries.

Only RetryableError is retried. FatalError propagates immediately. After
MAX_DISPATCH_ATTEMPTS total attempts the order is handed to the caller as
permanently undeliverable (DispatchExhausted) so the pipeline can
compensate — this module never silently drops an order.
"""

from __future__ import annotations

import time
import zlib
from dataclasses import dataclass
from typing import Callable

from . import config
from .errors import OrderError, RetryableError
from .ingest import Order
from .inventory import Reservation


class DispatchExhausted(OrderError):
    """Raised after the final dispatch attempt fails with a retryable error."""

    def __init__(self, last_error: RetryableError):
        super().__init__(f"gave up after {config.MAX_DISPATCH_ATTEMPTS} attempts")
        self.last_error = last_error


@dataclass(frozen=True)
class DispatchResult:
    carrier: str
    attempts: int


def choose_carrier(order: Order, reservation: Reservation) -> str:
    """Offshore orders always fly; heavy domestic parcels go by freight."""
    if order.region == "offshore":
        return "air"
    total_weight = sum(line.quantity * line.weight_g for line in reservation.lines)
    return "post" if total_weight <= config.POST_MAX_WEIGHT_G else "freight"


def backoff_ms(attempt: int, order_id: str) -> int:
    """Delay before ``attempt`` (2-based): BASE * 2^(attempt-2) plus a
    deterministic per-order jitter of 0-99 ms."""
    base = config.BASE_RETRY_DELAY_MS * (2 ** (attempt - 2))
    jitter = zlib.crc32(order_id.encode()) % 100
    return base + jitter


def dispatch(
    order: Order,
    reservation: Reservation,
    send: Callable[[str, Order], None],
    sleep: Callable[[float], None] = time.sleep,
) -> DispatchResult:
    carrier = choose_carrier(order, reservation)
    last_error: RetryableError | None = None

    for attempt in range(1, config.MAX_DISPATCH_ATTEMPTS + 1):
        if attempt > 1:
            sleep(backoff_ms(attempt, order.order_id) / 1000)
        try:
            send(carrier, order)
            return DispatchResult(carrier=carrier, attempts=attempt)
        except RetryableError as err:
            last_error = err

    assert last_error is not None
    raise DispatchExhausted(last_error)
