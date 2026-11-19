"""Service-level checkout, rollback, and stock alert tests."""

import tempfile
import unittest
from pathlib import Path

from backend.bootstrap import build_app_context
from backend.core.errors import InsufficientStockError, PaymentError
from backend.seed.demo_data import seed_retail


class SalesTests(unittest.TestCase):
    """Exercise the critical sale contract using a fresh local database."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.app = build_app_context(Path(self.temporary.name))
        self.app.setup.complete_setup("Test Business", "Retail Shop", "KES", "admin", "Administrator", "password123")
        self.app.auth.login("admin", "password123")
        self.item_id = seed_retail(self.app.catalog)[0]
        self.item = self.app.repository.get("items", self.item_id)

    def tearDown(self) -> None:
        self.app.close()
        self.temporary.cleanup()

    def test_selling_two_units_updates_stock_and_ledger(self) -> None:
        result = self.app.sales.process_sale(
            [{"item_id": self.item_id, "quantity_milli": 2000}],
            [{"method": "Cash", "amount_minor": self.item["price_minor"] * 2}],
        )
        self.assertEqual(self.app.repository.get("items", self.item_id)["stock_milli"], 8000)
        movements = self.app.inventory.stock_history(self.item_id)
        self.assertEqual(movements[-1]["quantity_delta_milli"], -2000)
        self.assertEqual(result.receipt_number[-4:], "0001")

    def test_oversell_rolls_back_sale_and_inventory(self) -> None:
        with self.assertRaises(InsufficientStockError):
            self.app.sales.process_sale(
                [{"item_id": self.item_id, "quantity_milli": 20_000}],
                [{"method": "Cash", "amount_minor": self.item["price_minor"] * 20}],
            )
        self.assertEqual(self.app.repository.get("items", self.item_id)["stock_milli"], 10_000)
        self.assertEqual(self.app.repository.find("sales"), [])
        self.assertEqual(self.app.repository.find("stock_movements", {"reason": "sale"}), [])

    def test_mpesa_payment_requires_reference(self) -> None:
        with self.assertRaises(PaymentError):
            self.app.sales.process_sale(
                [{"item_id": self.item_id, "quantity_milli": 1000}],
                [{"method": "M-Pesa", "amount_minor": self.item["price_minor"]}],
            )
        self.assertEqual(self.app.repository.get("items", self.item_id)["stock_milli"], 10_000)

    def test_held_sales_can_be_listed_and_recalled(self) -> None:
        held_id = self.app.sales.hold_sale(
            [{"item_id": self.item_id, "quantity_milli": 1250}], note="Customer pickup"
        )
        listed = self.app.sales.list_held()
        self.assertEqual(listed[0]["id"], held_id)
        self.assertEqual(listed[0]["lines"][0]["quantity_milli"], 1250)
        recalled = self.app.sales.recall_held(held_id)
        self.assertEqual(recalled["note"], "Customer pickup")
        self.assertEqual(recalled["lines"][0]["item_id"], self.item_id)
        self.assertEqual(self.app.sales.list_held(), [])
        self.assertEqual(self.app.repository.get("items", self.item_id)["stock_milli"], 10_000)

    def test_low_stock_event_fires_once_on_threshold_crossing(self) -> None:
        events = []
        self.app.events.subscribe("low_stock_alert", lambda event: events.append(event.payload))
        price = self.item["price_minor"]
        self.app.sales.process_sale(
            [{"item_id": self.item_id, "quantity_milli": 8000}],
            [{"method": "Cash", "amount_minor": price * 8}],
        )
        self.app.inventory.adjust_stock(self.item_id, -1000, "shrinkage")
        self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
