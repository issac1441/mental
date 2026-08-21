import time
import unittest

from orderflow.dispatch import backoff_ms
from orderflow.errors import CarrierTimeout
from orderflow.inventory import Inventory
from orderflow.pipeline import Pipeline

CATALOG = {
    "WIDGET": {"price_cents": 3000_00, "stock": 10, "weight_g": 500},
    "ANVIL": {"price_cents": 900_00, "stock": 2, "weight_g": 4000},
}


def make_pipeline(send):
    inventory = Inventory()
    inventory.load_catalog(CATALOG)
    return Pipeline(inventory=inventory, send=send)


class PipelineTests(unittest.TestCase):
    def test_happy_path_dispatches_with_totals(self):
        pipeline = make_pipeline(lambda carrier, order: None)
        receipt = pipeline.process(
            {"order_id": "o-1", "lines": [{"sku": "WIDGET", "quantity": 3}]}
        )
        self.assertEqual(receipt.status, "dispatched")
        # 9000.00 subtotal, spring-30 applies -> 6300.00, tax 315.00,
        # shipping free because the PRE-discount subtotal beats the threshold.
        self.assertEqual(receipt.total_cents, 6615_00)

    def test_free_shipping_uses_pre_discount_subtotal(self):
        pipeline = make_pipeline(lambda carrier, order: None)
        receipt = pipeline.process(
            {"order_id": "o-2", "lines": [{"sku": "WIDGET", "quantity": 3}]}
        )
        # Discounted goods total (6300.00) is below the 8000.00 threshold,
        # yet shipping is still free: eligibility is checked before discount.
        self.assertEqual(receipt.total_cents, 6615_00)

    def test_insufficient_stock_fails_without_retry(self):
        calls = []
        pipeline = make_pipeline(lambda carrier, order: calls.append(carrier))
        receipt = pipeline.process(
            {"order_id": "o-3", "lines": [{"sku": "ANVIL", "quantity": 5}]}
        )
        self.assertEqual(receipt.status, "failed")
        self.assertIn("ANVIL", receipt.reason)
        self.assertEqual(calls, [])  # dispatch never ran

    def test_dead_letter_after_exhausted_retries_releases_stock(self):
        def always_timeout(carrier, order):
            raise CarrierTimeout("carrier down")

        pipeline = make_pipeline(always_timeout)
        pipeline.send = always_timeout
        receipt = pipeline.process(
            {"order_id": "o-4", "lines": [{"sku": "ANVIL", "quantity": 2}]}
        )
        self.assertEqual(receipt.status, "dead_lettered")
        self.assertEqual(len(pipeline.dead_letters), 1)
        stock = pipeline.inventory.store.get("catalog/ANVIL").value["stock"]
        self.assertEqual(stock, 2)  # reservation was released

    def test_backoff_doubles_with_stable_jitter(self):
        jitter = backoff_ms(2, "o-5") - 200
        self.assertGreaterEqual(jitter, 0)
        self.assertLess(jitter, 100)
        self.assertEqual(backoff_ms(3, "o-5"), 400 + jitter)

    def test_expired_reservation_is_rebuilt_and_flags_reprice(self):
        inventory = Inventory()
        inventory.load_catalog(CATALOG)
        order_raw = {"order_id": "o-6", "lines": [{"sku": "WIDGET", "quantity": 1}]}

        from orderflow.ingest import parse_order

        order = parse_order(order_raw)
        first = inventory.reserve(order, now=time.monotonic())
        self.assertFalse(first.reprice_required)

        # Fast-forward past the TTL: the reservation is rebuilt with current
        # catalog prices and marked reprice_required.
        later = first.created_at + 121
        second = inventory.reserve(order, now=later)
        self.assertTrue(second.reprice_required)


if __name__ == "__main__":
    unittest.main()
