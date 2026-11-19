"""Render reusable Qt widgets offscreen and verify their visual construction."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QScrollArea, QVBoxLayout, QWidget

from backend.bootstrap import build_app_context
from backend.core.money import fmt
from backend.models.cart import Cart
from gui.app import create_application
from gui.dialogs.payment import PaymentDialog
from gui.widgets import (
    CartLineItem, CategoryChip, KpiCard, ModuleToggleRow, ProductCard,
    QuantityStepper, ReceiptWidget, SearchField, SideDrawer, SidebarNavItem,
    StatusPill, Toast,
)


def main() -> int:
    """Build and render each foundation widget from real backend service data."""
    with tempfile.TemporaryDirectory(prefix="pos-gallery-") as directory:
        context = build_app_context(Path(directory))
        try:
            context.setup.complete_setup(
                "Gallery Business", "Retail Shop", "KES", "admin", "Administrator",
                "gallery-password", sample_data=True,
            )
            context.auth.login("admin", "gallery-password")
            item = context.catalog.search_items(limit=1)[0]
            currency = context.settings.get("currency")
            if not currency:
                raise RuntimeError("The gallery business currency is not configured.")
            lines = [{"item_id": item["id"], "quantity_milli": 1000}]
            quote = context.sales.quote_sale(lines)
            sale = context.sales.process_sale(
                lines, [{"method": "Cash", "amount_minor": quote["total_minor"]}]
            )
            application, bridge = create_application(context, [])
            bridge.event_received.connect(lambda *_: None)
            window = QMainWindow()
            window.setWindowTitle("POS widget gallery")
            window.resize(1280, 760)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            page = QWidget()
            content = QVBoxLayout(page)
            row = QHBoxLayout()
            nav = SidebarNavItem("dashboard", "Dashboard", "dashboard")
            nav.set_active(True)
            nav.navigation_requested.connect(lambda _: nav.set_active(True))
            metrics = context.reports.dashboard_kpis()
            kpi = KpiCard("Sales today", fmt(metrics["sales_minor"], currency))
            product = ProductCard(item, currency)
            cart_line = dict(quote["lines"][0])
            cart = Cart()
            cart.add(item["id"], 1000)
            product.add_requested.connect(cart.add)
            chip = CategoryChip("all", "All items")
            chip.setChecked(True)
            chip.category_selected.connect(lambda _: context.catalog.search_items())
            stepper = QuantityStepper()
            stepper.quantity_changed.connect(
                lambda quantity: cart.set_quantity(item["id"], quantity) if len(cart) else None
            )
            status = StatusPill("In stock")
            search = SearchField()
            search.textChanged.connect(context.catalog.search_items)
            module = ModuleToggleRow("barcode", "Barcode support")
            module.module_changed.connect(lambda key, enabled: context.settings.set_modules({key: enabled}))
            for widget in (nav, kpi, product, chip, stepper, status, search, module):
                row.addWidget(widget)
            content.addLayout(row)
            line_widget = CartLineItem(cart_line, currency)
            line_widget.quantity_changed.connect(cart.set_quantity)
            line_widget.remove_requested.connect(cart.remove)
            content.addWidget(line_widget)
            drawer = SideDrawer("Item details", page)
            drawer.content_layout.addWidget(QLabel(item["name"]))
            drawer.open()
            content.addWidget(drawer)
            receipt = ReceiptWidget(context.receipts, sale.id)
            content.addWidget(receipt)
            toast = Toast(window)
            toast.show_message("Gallery ready")
            content.addWidget(toast)
            scroll.setWidget(page)
            window.setCentralWidget(scroll)
            window.show()
            application.processEvents()

            dialog = PaymentDialog(
                context.sales, lines, context.sales.quote_sale(lines),
                [row["name"] for row in context.settings.payment_methods() if row["active"]],
                currency=currency, parent=window,
            )
            dialog.show()
            application.processEvents()
            images = [window.grab(), nav.grab(), kpi.grab(), product.grab(),
                      chip.grab(), stepper.grab(), status.grab(), search.grab(),
                      module.grab(), receipt.grab(), dialog.grab()]
            if any(image.isNull() for image in images):
                raise RuntimeError("One or more GUI widgets failed to render.")
            screenshot_dir = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(screenshot_dir / "widget-gallery.png"))
            dialog.close()
            window.close()
            bridge.unsubscribe()
            application.processEvents()
            print(f"Rendered {len(images)} GUI surfaces offscreen.")
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
