"""Inventory reservation.

A reservation freezes two things for an order: the stock it will consume and
the unit prices it will be billed at. Reservations are idempotent per
order_id — re-processing the same order returns the existing reservation
while it is still live. Once the TTL lapses, the reservation is rebuilt from
the current catalog and flagged ``reprice_required``, because the captured
unit prices may have changed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config
from .errors import InsufficientStock, UnknownSku, VersionConflict
from .ingest import Order
from .store import VersionedStore

_PUT_ATTEMPTS = 3


@dataclass(frozen=True)
class ReservedLine:
    sku: str
    quantity: int
    unit_price_cents: int
    weight_g: int


@dataclass
class Reservation:
    order_id: str
    lines: tuple[ReservedLine, ...]
    created_at: float
    reprice_required: bool = False

    def expired(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return now - self.created_at > config.RESERVATION_TTL_SECONDS


@dataclass
class Inventory:
    """Catalog plus live reservations, both kept in the versioned store."""

    store: VersionedStore = field(default_factory=VersionedStore)

    def load_catalog(self, catalog: dict[str, dict]) -> None:
        for sku, entry in catalog.items():
            self.store.put(f"catalog/{sku}", dict(entry), expected_version=None)

    def reserve(self, order: Order, now: float | None = None) -> Reservation:
        """Reserve stock and capture unit prices for ``order``.

        Idempotent per order_id. An expired reservation is replaced by a
        fresh one built from current catalog prices, with
        ``reprice_required`` set so the pipeline knows totals must be
        recomputed.
        """
        key = f"reservation/{order.order_id}"
        existing = self.store.get(key)
        if existing is not None:
            reservation: Reservation = existing.value
            if not reservation.expired(now):
                return reservation
            rebuilt = self._build(order, now)
            rebuilt.reprice_required = True
            self._put_with_retry(key, rebuilt, existing.version)
            return rebuilt

        reservation = self._build(order, now)
        self._put_with_retry(key, reservation, None)
        return reservation

    def release(self, order_id: str) -> None:
        """Return reserved stock to the catalog and drop the reservation."""
        key = f"reservation/{order_id}"
        existing = self.store.get(key)
        if existing is None:
            return
        reservation: Reservation = existing.value
        for line in reservation.lines:
            record = self.store.get(f"catalog/{line.sku}")
            if record is None:
                continue
            entry = dict(record.value)
            entry["stock"] += line.quantity
            self.store.put(f"catalog/{line.sku}", entry, record.version)
        self.store.delete(key)

    def _build(self, order: Order, now: float | None) -> Reservation:
        # Validate every line before committing anything, so a failed
        # reservation leaves no partial stock to unwind.
        checked = []
        for line in order.lines:
            record = self.store.get(f"catalog/{line.sku}")
            if record is None:
                raise UnknownSku(line.sku)
            entry = record.value
            if entry["stock"] < line.quantity:
                raise InsufficientStock(
                    f"{line.sku}: want {line.quantity}, have {entry['stock']}"
                )
            checked.append((line, record))

        reserved = []
        for line, record in checked:
            entry = dict(record.value)
            entry["stock"] -= line.quantity
            self._put_with_retry(f"catalog/{line.sku}", entry, record.version)
            reserved.append(
                ReservedLine(
                    sku=line.sku,
                    quantity=line.quantity,
                    unit_price_cents=entry["price_cents"],
                    weight_g=entry["weight_g"],
                )
            )
        return Reservation(
            order_id=order.order_id,
            lines=tuple(reserved),
            created_at=time.monotonic() if now is None else now,
        )

    def _put_with_retry(self, key: str, value, expected_version) -> None:
        for attempt in range(1, _PUT_ATTEMPTS + 1):
            try:
                self.store.put(key, value, expected_version)
                return
            except VersionConflict:
                if attempt == _PUT_ATTEMPTS:
                    raise
                fresh = self.store.get(key)
                expected_version = fresh.version if fresh else None
