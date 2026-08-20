"""Parse and validate raw order payloads into Order objects."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationError

_ALLOWED_REGIONS = {"domestic", "offshore"}


@dataclass(frozen=True)
class Line:
    sku: str
    quantity: int


@dataclass(frozen=True)
class Order:
    order_id: str
    region: str
    lines: tuple[Line, ...]


def parse_order(raw: dict) -> Order:
    """Turn a raw dict into an Order or raise ValidationError (fatal)."""
    order_id = raw.get("order_id")
    if not order_id or not isinstance(order_id, str):
        raise ValidationError("order_id is required")

    region = raw.get("region", "domestic")
    if region not in _ALLOWED_REGIONS:
        raise ValidationError(f"unknown region: {region!r}")

    raw_lines = raw.get("lines") or []
    if not raw_lines:
        raise ValidationError("an order needs at least one line")

    lines = []
    for item in raw_lines:
        sku = item.get("sku")
        quantity = item.get("quantity", 0)
        if not sku or not isinstance(sku, str):
            raise ValidationError("every line needs a sku")
        if not isinstance(quantity, int) or quantity < 1:
            raise ValidationError(f"{sku}: quantity must be a positive integer")
        lines.append(Line(sku=sku, quantity=quantity))

    return Order(order_id=order_id, region=region, lines=tuple(lines))
