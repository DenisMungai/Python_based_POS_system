"""Capture fresh setup and service-backed release screenshots for two presets."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from backend.bootstrap import build_app_context
from gui.app import create_application
from gui.dialogs.sale_complete import SaleCompleteDialog
from gui.dialogs.setup import SetupDialog
from gui.shell import AppWindow


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "docs" / "screenshots" / "release"


def save_widget(widget: QWidget, filename: str) -> None:
    image = widget.grab()
    if image.isNull() or not image.save(str(SCREENSHOT_DIR / filename)):
        raise RuntimeError(f"Could not capture screenshot: {filename}")


def capture_preset(preset: str, prefix: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"pos-release-{prefix}-") as directory:
        context = build_app_context(Path(directory))
        bridge = None
        window = None
        try:
            context.setup.complete_setup(
                f"{prefix.title()} Demo", preset, "KES", "admin", "Administrator",
                "release-screenshot-password", sample_data=True,
            )
            context.auth.login("admin", "release-screenshot-password")
            context.auth.change_password(
                "release-screenshot-password", "release-screenshot-password-new",
            )
            application, bridge = create_application(context, [])
            window = AppWindow(context, bridge)
            window.resize(1280, 760)
            window.show()
            application.processEvents()
            save_widget(window, f"{prefix}-dashboard.png")

            for route, filename in (
                ("sales", f"{prefix}-sales.png"),
                ("products", f"{prefix}-products.png"),
            ):
                if route not in window.navigation:
                    raise RuntimeError(f"Missing {route} screen for {preset}.")
                window.navigation[route].click()
                application.processEvents()
                save_widget(window, filename)

            item = context.catalog.search_items(limit=1)[0]
            payment_method = next(
                str(row["name"]) for row in context.settings.payment_methods()
                if row["active"] and row["name"] == "Cash"
            )
            sale_lines = [{"item_id": int(item["id"]), "quantity_milli": 1000}]
            customer_id = context.customers.register(
                "Release Sample Customer", "555-0100", "sample@example.test",
            )
            context.customers.add_store_credit(customer_id, 500)
            context.discounts.create_voucher("LOCAL-SAMPLE", "fixed", 100)
            context.sales.hold_sale(sale_lines, customer_id=customer_id, note="Screenshot order")
            quote = context.sales.quote_sale(sale_lines)
            sale = context.sales.process_sale(
                sale_lines,
                [{"method": payment_method, "amount_minor": int(quote["total_minor"])}],
                customer_id=customer_id,
            )
            context.returns.create_return(
                sale.id,
                [{"sale_item_id": int(sale.items[0]["id"]), "quantity_milli": 250}],
                restock=False, note="Screenshot return",
            )
            for route in (
                "orders", "customers", "sales_history", "returns", "discounts",
                "reports", "users", "settings",
            ):
                if route not in window.navigation:
                    raise RuntimeError(f"Missing {route} screen for {preset}.")
                window.navigation[route].click()
                application.processEvents()
                save_widget(window, f"{prefix}-{route}.png")
            receipt = SaleCompleteDialog(context, sale)
            receipt.show()
            QTest.qWait(1200)
            application.processEvents()
            if not receipt.done_button.isEnabled():
                raise RuntimeError(f"Receipt animation did not finish for {preset}.")
            save_widget(receipt, f"{prefix}-receipt.png")
            receipt.close()
            window.close()
            bridge.unsubscribe()
            application.processEvents()
        finally:
            if window is not None:
                window.close()
            if bridge is not None:
                bridge.unsubscribe()
            context.close()


def main() -> int:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pos-release-setup-") as directory:
        context = build_app_context(Path(directory))
        try:
            application, bridge = create_application(context, [])
            setup = SetupDialog(context)
            setup.show()
            application.processEvents()
            save_widget(setup, "setup.png")
            setup.close()
            bridge.unsubscribe()
        finally:
            context.close()

    if QApplication.instance() is None:
        raise RuntimeError("Qt application initialization failed.")
    capture_preset("Retail Shop", "retail")
    capture_preset("Café / Restaurant", "cafe")
    print(f"Captured setup and two-preset release screenshots in {SCREENSHOT_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
