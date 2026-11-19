"""Regression tests for backend workflows beyond the central stock invariant."""

import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from backend.bootstrap import build_app_context
from backend.core.errors import (
    AccountLockedError, AuthenticationError, DuplicateError, ImportErrorReport, PaymentError,
    PermissionDeniedError, ValidationError, VoucherError,
)
from backend.models.cart import Cart


class WorkflowTests(unittest.TestCase):
    """Create an isolated configured app for each workflow test."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.app = build_app_context(Path(self.temporary.name))
        self.app.setup.complete_setup("Test", "Retail Shop", "KES", "admin", "Admin", "password123")
        self.admin = self.app.auth.login("admin", "password123")

    def tearDown(self) -> None:
        self.app.close()
        self.temporary.cleanup()

    def test_split_payment_and_voucher_update_saved_totals(self) -> None:
        item_id = self.app.catalog.create_item("Monitor", 10_000, stock_milli=3000)
        voucher_id = self.app.discounts.create_voucher("LESS1", "fixed", 1000)
        lines = [{"item_id": item_id, "quantity_milli": 1000}]
        quote = self.app.sales.quote_sale(lines, voucher_code="LESS1")
        sale = self.app.sales.process_sale(
            lines,
            [{"method": "Cash", "amount_minor": 5000},
             {"method": "M-Pesa", "amount_minor": 4000, "reference": "TEST-REF"}],
            voucher_code="LESS1",
        )
        self.assertEqual(sale.total_minor, 9000)
        self.assertEqual(quote["total_minor"], sale.total_minor)
        self.assertEqual(self.app.repository.get("vouchers", voucher_id)["used_count"], 1)

    def test_voucher_reduces_taxable_base_and_saved_tax(self) -> None:
        tax_id = self.app.settings.set_tax_rate("VAT", 1600, is_default=True)
        item_id = self.app.catalog.create_item(
            "Taxed item", 10_000, tax_rate_id=tax_id, stock_milli=1000
        )
        self.app.discounts.create_voucher("TEN-PERCENT", "percent", 1000)
        sale = self.app.sales.process_sale(
            [{"item_id": item_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 10_440}],
            voucher_code="TEN-PERCENT",
        )
        self.assertEqual(sale.discount_minor, 1000)
        self.assertEqual(sale.tax_minor, 1440)
        self.assertEqual(sale.total_minor, 10_440)

    def test_tax_inclusive_and_exclusive_sales_are_calculated(self) -> None:
        tax_id = self.app.settings.set_tax_rate("VAT", 1600, is_default=True)
        inclusive_id = self.app.catalog.create_item(
            "Inclusive", 11_600, tax_rate_id=tax_id, tax_inclusive=1, stock_milli=1000
        )
        exclusive_id = self.app.catalog.create_item(
            "Exclusive", 10_000, tax_rate_id=tax_id, stock_milli=1000
        )
        sale = self.app.sales.process_sale(
            [{"item_id": inclusive_id, "quantity_milli": 1000},
             {"item_id": exclusive_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 23_200}],
        )
        self.assertEqual(sale.tax_minor, 3200)
        self.assertEqual(sale.total_minor, 23_200)

    def test_return_and_void_restore_stock_with_ledger_entries(self) -> None:
        item_id = self.app.catalog.create_item("Cable", 1000, stock_milli=5000)
        sale = self.app.sales.process_sale(
            [{"item_id": item_id, "quantity_milli": 2000}],
            [{"method": "Cash", "amount_minor": 2000}],
        )
        line = sale.items[0]
        self.app.returns.create_return(sale.id, [{"sale_item_id": line["id"], "quantity_milli": 1000}])
        self.assertEqual(self.app.repository.get("items", item_id)["stock_milli"], 4000)
        self.app.sales.void_sale(sale.id, "Duplicate transaction")
        self.assertEqual(self.app.repository.get("items", item_id)["stock_milli"], 5000)
        self.assertEqual(self.app.repository.get("sales", sale.id)["status"], "voided")

    def test_return_restock_choice_is_respected_per_line_and_history_is_listed(self) -> None:
        first_id = self.app.catalog.create_item("Restock item", 1000, stock_milli=3000)
        second_id = self.app.catalog.create_item("No-restock item", 1000, stock_milli=3000)
        sale = self.app.sales.process_sale(
            [{"item_id": first_id, "quantity_milli": 1000},
             {"item_id": second_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 2000}],
        )
        self.app.returns.create_return(
            sale.id,
            [{"sale_item_id": sale.items[0]["id"], "quantity_milli": 1000, "restock": True},
             {"sale_item_id": sale.items[1]["id"], "quantity_milli": 1000, "restock": False}],
        )
        self.assertEqual(self.app.repository.get("items", first_id)["stock_milli"], 3000)
        self.assertEqual(self.app.repository.get("items", second_id)["stock_milli"], 2000)
        history = self.app.returns.list_returns()
        self.assertEqual(history[0]["receipt_number"], sale.receipt_number)
        self.assertEqual(history[0]["return_number"].split("-")[0], "RET")

    def test_bundle_reduces_component_stock_and_service_skips_stock(self) -> None:
        component_id = self.app.catalog.create_item("Bottle", 300, stock_milli=5000)
        bundle_id = self.app.catalog.create_item("Pack", 1000, item_type="bundle")
        self.app.catalog.set_bundle_components(
            bundle_id, [{"item_id": component_id, "quantity_milli": 2000}]
        )
        service_id = self.app.catalog.create_item("Installation", 5000, item_type="service")
        sale = self.app.sales.process_sale(
            [{"item_id": bundle_id, "quantity_milli": 2000},
             {"item_id": service_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 7000}],
        )
        self.assertEqual(self.app.repository.get("items", component_id)["stock_milli"], 1000)
        self.assertEqual(self.app.repository.get("items", service_id)["stock_milli"], 0)
        self.assertEqual(len(sale.items), 2)

    def test_authentication_lockout_and_permission_checks(self) -> None:
        self.app.auth.logout()
        for _ in range(4):
            with self.assertRaises(AuthenticationError):
                self.app.auth.login("admin", "wrong-password")
        with self.assertRaises(AccountLockedError):
            self.app.auth.login("admin", "wrong-password")
        with self.assertRaises(PermissionDeniedError):
            self.app.auth.require_permission("sales.process")

    def test_presets_change_terminology_without_code_changes(self) -> None:
        self.app.setup.apply_preset("Café / Restaurant")
        self.assertEqual(self.app.settings.term("customer"), "Guest")
        self.app.setup.apply_preset("Salon / Barber")
        self.assertEqual(self.app.settings.term("item"), "Service")
        self.assertTrue(self.app.settings.modules()["services_appointments"])

    def test_category_listing_is_service_backed_and_name_sorted(self) -> None:
        self.app.catalog.create_category("Zebra")
        self.app.catalog.create_category("Apples")
        self.assertEqual(
            [row["name"] for row in self.app.catalog.list_categories()],
            ["Accessories", "Apples", "Electronics", "General", "Zebra"],
        )

    def test_sql_injection_text_is_plain_catalog_data_and_import_is_dry_run(self) -> None:
        name = "x' OR 1=1 --"
        item_id = self.app.catalog.create_item(name, 100, stock_milli=1000)
        self.assertEqual(self.app.catalog.search_items(name)[0]["id"], item_id)
        preview = self.app.imports.preview_items_csv(
            "name,price_minor,quantity_milli\nImported,250,1000\n"
        )
        self.assertEqual(len(preview["rows"]), 1)
        self.assertEqual(self.app.repository.find("items", {"name": "Imported"}), [])
        with self.assertRaises(ImportErrorReport):
            self.app.imports.import_items_csv("name,price_minor,quantity_milli\n,not-number,-1\n")

    def test_customer_import_preview_is_non_mutating_and_export_round_trips(self) -> None:
        preview = self.app.imports.preview_customers_csv(
            "name,phone,email\nAmina,0712345678,amina@example.test\n"
        )
        self.assertEqual(len(preview["rows"]), 1)
        self.assertEqual(self.app.repository.find("customers"), [])
        imported = self.app.imports.import_customers_csv(
            "name,phone,email\nAmina,0712345678,amina@example.test\n", dry_run=False
        )
        self.assertEqual(len(imported["created_ids"]), 1)
        with tempfile.TemporaryDirectory() as output:
            path = self.app.imports.export_customers_csv(Path(output) / "customers.csv")
            self.assertIn("Amina", path.read_text(encoding="utf-8-sig"))

    def test_customer_csv_import_uses_customer_write_permission(self) -> None:
        self.app.auth.create_user("cashier", "Cashier", "Cashier", "cashier-password")
        self.app.auth.login("cashier", "cashier-password")
        imported = self.app.imports.import_customers_csv(
            "name,phone\nNew customer,555\n", dry_run=False
        )
        self.assertEqual(len(imported["created_ids"]), 1)
        with self.assertRaises(PermissionDeniedError):
            self.app.imports.import_items_csv(
                "name,price_minor,quantity_milli\nNew item,100,1000\n", dry_run=False
            )

    def test_range_report_returns_totals_series_and_breakdowns(self) -> None:
        item_id = self.app.catalog.create_item("Report item", 1250, stock_milli=1000)
        self.app.sales.process_sale(
            [{"item_id": item_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 1250}],
        )
        day = datetime.now(timezone.utc).date().isoformat()
        next_day = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        report = self.app.reports.range_report(
            f"{day}T00:00:00+00:00", f"{next_day}T00:00:00+00:00"
        )
        self.assertEqual(report["sales_minor"], 1250)
        self.assertEqual(report["orders"], 1)
        self.assertEqual(report["series"][0]["sales_minor"], 1250)
        self.assertEqual(report["payments"][0]["method"], "Cash")

    def test_backup_restore_round_trip(self) -> None:
        original_id = self.app.catalog.create_item("Before backup", 500, stock_milli=1000)
        backup = self.app.backups.create_backup()
        self.app.catalog.create_item("After backup", 700, stock_milli=1000)
        self.app.backups.restore_backup(backup)
        self.assertIsNotNone(self.app.repository.get("items", original_id))
        self.assertEqual(self.app.repository.find("items", search="After backup", search_fields=("name",)), [])

    def test_auth_password_change_and_service_permission_enforcement(self) -> None:
        self.assertTrue(self.admin.must_change_password)
        self.app.auth.change_password("password123", "new-password456")
        self.assertFalse(self.app.auth.current_user.must_change_password)
        manager_id = self.app.auth.create_user("manager", "Manager", "Manager", "manager-password")
        self.assertGreater(manager_id, 0)
        self.app.auth.login("manager", "manager-password")
        with self.assertRaises(PermissionDeniedError):
            self.app.settings.set("currency", "USD")

    def test_admin_can_update_own_profile_and_password(self) -> None:
        self.app.auth.update_profile(
            "password123", "  ADMIN-NEW ", " New Admin ", "updated-password456"
        )
        updated = self.app.auth.current_user
        self.assertIsNotNone(updated)
        self.assertEqual(updated.username, "admin-new")
        self.assertEqual(updated.display_name, "New Admin")
        self.assertFalse(updated.must_change_password)
        saved = self.app.repository.get("users", self.admin.id)
        self.assertEqual(saved["username"], "admin-new")
        self.assertEqual(saved["display_name"], "New Admin")

        self.app.auth.logout()
        logged_in = self.app.auth.login("admin-new", "updated-password456")
        self.assertEqual(logged_in.display_name, "New Admin")

    def test_admin_profile_update_requires_current_password_and_unique_username(self) -> None:
        self.app.auth.create_user("other", "Other User", "Manager", "other-password")
        with self.assertRaises(AuthenticationError):
            self.app.auth.update_profile(
                "wrong-password", "renamed-admin", "Admin", "another-password"
            )
        with self.assertRaises(DuplicateError):
            self.app.auth.update_profile("password123", "other", "Admin")
        self.assertEqual(self.app.auth.current_user.username, "admin")

    def test_non_admin_cannot_use_admin_profile_update(self) -> None:
        self.app.auth.create_user("manager", "Manager", "Manager", "manager-password")
        self.app.auth.login("manager", "manager-password")
        with self.assertRaises(PermissionDeniedError):
            self.app.auth.update_profile(
                "manager-password", "manager-new", "Manager", "new-manager-password"
            )

    def test_administrator_pin_verifies_and_business_sample_is_preset_specific(self) -> None:
        pin_user = self.app.auth.create_user(
            "pin-admin", "PIN Admin", "Admin", "another-password", pin="2468"
        )
        self.assertGreater(pin_user, 0)
        self.app.auth.login("pin-admin", "another-password")
        self.assertTrue(self.app.auth.verify_admin_pin("2468"))

        with tempfile.TemporaryDirectory() as directory:
            salon = build_app_context(Path(directory))
            try:
                salon.setup.complete_setup(
                    "Studio", "Salon / Barber", "KES", "owner", "Owner",
                    "owner-password", sample_data=True,
                )
                items = salon.repository.find("items", order_by="id")
                self.assertEqual(items[0]["item_type"], "service")
                self.assertEqual(items[0]["name"], "Haircut")
            finally:
                salon.close()

    def test_expiry_batches_update_stock_and_report_horizon(self) -> None:
        item_id = self.app.catalog.create_item("Medicine", 250, stock_milli=0)
        self.app.inventory.add_expiry_batch(item_id, "B-1", "2026-11-20", 5000)
        expiring = self.app.inventory.expiring_items(10)
        self.assertEqual(expiring[0]["item_id"], item_id)
        self.assertEqual(self.app.repository.get("items", item_id)["stock_milli"], 5000)

    def test_cart_quantities_are_intent_only_and_weighed_sales_use_milli_units(self) -> None:
        cart = Cart()
        item_id = self.app.catalog.create_item(
            "Bulk rice", 1000, item_type="weighed", unit="kg", stock_milli=3000
        )
        cart.add(item_id, 1250)
        sale = self.app.sales.process_sale(
            cart.to_sale_lines(), [{"method": "Cash", "amount_minor": 1250}]
        )
        self.assertEqual(sale.total_minor, 1250)
        self.assertEqual(self.app.repository.get("items", item_id)["stock_milli"], 1750)
        cart.clear()
        self.assertEqual(len(cart), 0)

    def test_cash_change_and_underpayment_validation(self) -> None:
        item_id = self.app.catalog.create_item("Pen", 500, stock_milli=2000)
        with self.assertRaises(PaymentError):
            self.app.sales.process_sale(
                [{"item_id": item_id, "quantity_milli": 1000}],
                [{"method": "Cash", "amount_minor": 400}],
            )
        sale = self.app.sales.process_sale(
            [{"item_id": item_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 700}],
        )
        self.assertEqual(sale.change_minor, 200)

    def test_voucher_expiry_and_maximum_uses_are_enforced(self) -> None:
        self.app.discounts.create_voucher(
            "EXPIRED", "fixed", 100, expires_at="2020-01-01T00:00:00+00:00"
        )
        self.app.discounts.create_voucher("ONCE", "fixed", 100, max_uses=1)
        with self.assertRaises(VoucherError):
            self.app.discounts.validate_voucher("EXPIRED", 1000)
        self.app.discounts.validate_voucher("ONCE", 1000)
        self.app.repository.update("vouchers", self.app.repository.find("vouchers", {"code": "ONCE"})[0]["id"],
                                   {"used_count": 1})
        with self.assertRaises(VoucherError):
            self.app.discounts.validate_voucher("ONCE", 1000)

    def test_returns_reject_over_return_and_can_skip_restock(self) -> None:
        item_id = self.app.catalog.create_item("Notebook", 1200, stock_milli=3000)
        sale = self.app.sales.process_sale(
            [{"item_id": item_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 1200}],
        )
        sale_line = sale.items[0]
        with self.assertRaises(ValidationError):
            self.app.returns.create_return(
                sale.id, [{"sale_item_id": sale_line["id"], "quantity_milli": 2000}]
            )
        self.app.returns.create_return(
            sale.id, [{"sale_item_id": sale_line["id"], "quantity_milli": 1000}], restock=False
        )
        self.assertEqual(self.app.repository.get("items", item_id)["stock_milli"], 2000)

    def test_receipt_numbers_increment_and_reports_match_sales(self) -> None:
        item_id = self.app.catalog.create_item("Cup", 800, stock_milli=3000)
        moment = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
        receipts = []
        for _ in range(2):
            sale = self.app.sales.process_sale(
                [{"item_id": item_id, "quantity_milli": 1000}],
                [{"method": "Cash", "amount_minor": 800}],
                at=moment,
            )
            receipts.append(sale.receipt_number)
        self.assertTrue(receipts[0].endswith("0001"))
        self.assertTrue(receipts[1].endswith("0002"))
        monthly = self.app.reports.monthly_report(2026, 11)
        self.assertEqual(monthly["orders"], 2)
        self.assertEqual(self.app.reports.top_items("2026-11-01", "2026-12-01")[0]["name"], "Cup")

    def test_receipt_text_is_itemized_and_includes_payment_summary(self) -> None:
        item_id = self.app.catalog.create_item("Coffee Beans", 1250, stock_milli=2000)
        sale = self.app.sales.process_sale(
            [{"item_id": item_id, "quantity_milli": 1000}],
            [{"method": "Cash", "amount_minor": 1500}],
        )
        receipt = self.app.receipts.render_text(sale.id)
        self.assertIn("Coffee Beans", receipt)
        self.assertIn("1 x KES 12.50", receipt)
        self.assertIn("Subtotal", receipt)
        self.assertIn("Tax", receipt)
        self.assertIn("TOTAL", receipt)
        self.assertIn("Cash", receipt)
        self.assertIn("Change", receipt)
        with tempfile.TemporaryDirectory() as output:
            path = self.app.receipts.export_text(sale.id, Path(output) / "receipt.txt")
            self.assertEqual(path.read_text(encoding="utf-8"), receipt)


if __name__ == "__main__":
    unittest.main()
