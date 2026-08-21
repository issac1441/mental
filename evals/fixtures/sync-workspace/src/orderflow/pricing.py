"""Pricing.

Totals are computed from the reservation, not from the raw order: the
reservation carries the unit-price snapshot the order will actually be
billed at. Rules, in order:

1. Goods subtotal = sum of reserved quantity x captured unit price.
2. At most one discount applies — the highest-priority rule whose minimum
   subtotal is met. Discounts never stack.
3. Tax is charged on the goods subtotal before any discount. Shipping is
   never taxed.
4. Shipping is a flat fee, waived when the goods subtotal AFTER discount
   meets FREE_SHIPPING_THRESHOLD_CENTS. A large discount can therefore
   cost the order its free shipping.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config
from .inventory import Reservation


@dataclass(frozen=True)
class DiscountRule:
    name: str
    percent: int
    min_subtotal_cents: int
    priority: int


DISCOUNT_RULES = (
    DiscountRule("spring-30", percent=30, min_subtotal_cents=5000_00, priority=20),
    DiscountRule("loyalty-10", percent=10, min_subtotal_cents=0, priority=10),
)


@dataclass(frozen=True)
class Quote:
    subtotal_cents: int
    discount_name: str | None
    discount_cents: int
    tax_cents: int
    shipping_cents: int
    total_cents: int


def price(reservation: Reservation) -> Quote:
    subtotal = sum(l.quantity * l.unit_price_cents for l in reservation.lines)

    rule = _select_discount(subtotal)
    discount = subtotal * rule.percent // 100 if rule else 0
    discounted = subtotal - discount

    tax = round(subtotal * config.TAX_RATE)

    if discounted >= config.FREE_SHIPPING_THRESHOLD_CENTS:
        shipping = 0
    else:
        shipping = config.FLAT_SHIPPING_CENTS

    return Quote(
        subtotal_cents=subtotal,
        discount_name=rule.name if rule else None,
        discount_cents=discount,
        tax_cents=tax,
        shipping_cents=shipping,
        total_cents=discounted + tax + shipping,
    )


def _select_discount(subtotal_cents: int) -> DiscountRule | None:
    applicable = [
        rule for rule in DISCOUNT_RULES if subtotal_cents >= rule.min_subtotal_cents
    ]
    if not applicable:
        return None
    return max(applicable, key=lambda rule: rule.priority)
