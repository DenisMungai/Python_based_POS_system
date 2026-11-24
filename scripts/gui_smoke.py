"""Exercise a keyboard-only checkout through the real Qt and service layers."""

import os
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QToolButton

from backend.bootstrap import build_app_context
from gui.app import create_application
from gui.dialogs.change_password import ChangePasswordDialog
from gui.dialogs.login import LoginDialog
from gui.dialogs.payment import PaymentDialog
from gui.dialogs.profile import ProfileDialog
from gui.dialogs.sale_complete import SaleCompleteDialog
from gui.dialogs.setup import SetupDialog
from gui.shell import AppWindow
from gui.styles.tokens import DEFAULT_PALETTE, px
from gui.views.current_sale import CurrentSaleView
from gui.widgets import PRODUCT_TILE_RATIO, ProductCard, QuantityStepper, ReceiptWidget, cover_pixmap


def assert_table_actions_fit(table, row: int, column: int) -> None:
    """Ensure every visible action button fits inside its table cell."""
    actions = table.cellWidget(row, column)
    if actions is None or actions.layout() is None:
        raise RuntimeError("The table row did not create its actions cell.")
    if actions.width() < actions.layout().sizeHint().width():
        raise RuntimeError(
            "The table actions cell clips its contents: "
            f"cell={actions.width()}, layout={actions.layout().sizeHint().width()}, "
            f"column={table.columnWidth(column)}."
        )
    for button in actions.findChildren(QPushButton):
        if button.isVisible() and button.width() < button.sizeHint().width():
            raise RuntimeError(f"The {button.text()} action label is clipped.")


def assert_cover_pixmap_cases() -> None:
    """Verify cover crops preserve source geometry and return opaque exact-size tiles."""
    for source_width, source_height in ((200, 100), (100, 200), (160, 200)):
        image = QImage(source_width, source_height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#263238"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(
            source_width // 2 - 10, source_height // 2 - 10, 20, 20,
        )
        painter.end()

        result = cover_pixmap(QPixmap.fromImage(image), 120, 150)
        logical_size = result.deviceIndependentSize()
        if result.isNull() or logical_size.width() != 120 or logical_size.height() != 150:
            raise RuntimeError("Cover rendering did not return the exact logical tile size.")
        rendered = result.toImage()
        circle_points = [
            (x, y)
            for y in range(rendered.height())
            for x in range(rendered.width())
            if rendered.pixelColor(x, y).red() > 220
            and rendered.pixelColor(x, y).green() > 220
            and rendered.pixelColor(x, y).blue() > 220
        ]
        if not circle_points:
            raise RuntimeError("Cover rendering lost the centred source detail.")
        circle_width = max(x for x, _ in circle_points) - min(x for x, _ in circle_points) + 1
        circle_height = max(y for _, y in circle_points) - min(y for _, y in circle_points) + 1
        scale = max(120 / source_width, 150 / source_height)
        expected_diameter = 20 * scale * result.devicePixelRatio()
        if (
            abs(circle_width - circle_height) > 2
            or abs(circle_width - expected_diameter) > 2
        ):
            raise RuntimeError("Cover rendering stretched the source image.")
        if any(
            rendered.pixelColor(x, y).alpha() != 255
            for y in range(rendered.height())
            for x in range(rendered.width())
        ):
            raise RuntimeError("Cover rendering left transparent pixels in the tile.")


def main() -> int:
    """Create isolated data, launch the shell, and complete one real sale."""
    with tempfile.TemporaryDirectory(prefix="pos-gui-smoke-") as directory:
        context = build_app_context(Path(directory))
        application = None
        bridge = None
        try:
            application, bridge = create_application(context, [])
            if DEFAULT_PALETTE.primary != "#15A046":
                raise RuntimeError("The default primary accent is not the requested green.")
            if application.windowIcon().isNull():
                raise RuntimeError("The POS application icon did not load.")
            quantity_stepper = QuantityStepper(2000)
            if quantity_stepper.value_label.text() != "2":
                raise RuntimeError("The sale ticket quantity still shows trailing decimals.")
            quantity_stepper.set_quantity(1250)
            if quantity_stepper.value_label.text() != "1.25":
                raise RuntimeError("The sale ticket lost meaningful weighed-item precision.")
            screen = application.primaryScreen()
            if screen is None:
                raise RuntimeError("Qt did not expose a primary display.")
            expected_sidebar_width = max(
                1, round(232 * 0.9 / max(screen.devicePixelRatio(), 1.0))
            )
            if px(232) != expected_sidebar_width:
                raise RuntimeError("GUI dimensions are not compensating for display DPI.")
            assert_cover_pixmap_cases()

            setup = SetupDialog(context)
            setup.show()
            application.processEvents()
            setup.business_name.setFocus()
            QTest.keyClicks(setup.business_name, "GUI Smoke Shop")
            setup.currency.setFocus()
            QTest.keyClicks(setup.currency, "KES")
            setup.admin_name.setFocus()
            QTest.keyClicks(setup.admin_name, "Administrator")
            setup.username.setFocus()
            QTest.keyClicks(setup.username, "admin")
            setup.password.setFocus()
            QTest.keyClicks(setup.password, "smoke-password")
            setup.sample_data.setFocus()
            QTest.keyClick(setup.sample_data, Qt.Key.Key_Space)
            setup.create_button.setFocus()
            QTest.keyClick(setup.create_button, Qt.Key.Key_Space)
            if setup.result() != SetupDialog.DialogCode.Accepted:
                raise RuntimeError(setup.error_label.text() or "First-run setup did not complete.")

            login = LoginDialog(context)
            login.show()
            application.processEvents()
            login.username.setFocus()
            QTest.keyClicks(login.username, "admin")
            login.password.setFocus()
            QTest.keyClicks(login.password, "smoke-password")
            QTest.keyClick(login.password, Qt.Key.Key_Return)
            if login.result() != LoginDialog.DialogCode.Accepted:
                raise RuntimeError(login.error_label.text() or "Staff login did not complete.")

            change_password = ChangePasswordDialog(context)
            change_password.show()
            application.processEvents()
            change_password.current_password.setFocus()
            QTest.keyClicks(change_password.current_password, "smoke-password")
            change_password.new_password.setFocus()
            QTest.keyClicks(change_password.new_password, "smoke-password-new")
            change_password.confirm_password.setFocus()
            QTest.keyClicks(change_password.confirm_password, "smoke-password-new")
            QTest.keyClick(change_password.confirm_password, Qt.Key.Key_Return)
            user = context.auth.current_user
            if change_password.result() != ChangePasswordDialog.DialogCode.Accepted:
                raise RuntimeError(
                    change_password.error_label.text() or "First-login password update failed."
                )
            if user is None or user.must_change_password:
                raise RuntimeError("The initial-password requirement was not cleared.")

            window = AppWindow(context, bridge)
            window.resize(px(1280), px(760))
            window.show()
            application.processEvents()
            if window.windowTitle() != "GUI Smoke Shop Sale":
                raise RuntimeError("The POS window title contains an unexpected business/sale separator.")
            if window.windowIcon().isNull():
                raise RuntimeError("The POS shell did not inherit the application icon.")
            if window.width() != px(1280) or window.height() != px(760):
                raise RuntimeError("The POS shell did not open at its scaled design size.")
            profile_action = next(
                (button for button in window.findChildren(QPushButton)
                 if button.text() == "My profile"),
                None,
            )
            logout_action = next(
                (button for button in window.findChildren(QPushButton)
                 if button.text() == "Log out"),
                None,
            )
            if (
                profile_action is None or profile_action.icon().isNull()
                or logout_action is None or logout_action.icon().isNull()
            ):
                raise RuntimeError("Administrator account actions are not aligned with sidebar navigation.")
            topbar = window.findChild(QFrame, "topbar")
            if topbar is None:
                raise RuntimeError("The application topbar was not created.")
            welcome_top = window.welcome_title.mapTo(topbar, QPoint(0, 0)).y()
            welcome_bottom = (
                window.welcome_detail_label.mapTo(topbar, QPoint(0, 0)).y()
                + window.welcome_detail_label.height()
            )
            if welcome_top < px(30) or welcome_bottom > topbar.height() - px(14):
                raise RuntimeError("The welcome text is clipped or too close to the topbar edges.")

            if "products" not in window.navigation:
                raise RuntimeError("The products route was not available to the administrator.")
            expected_routes = (
                "dashboard", "products", "sales", "customers", "sales_history", "orders",
                "returns", "discounts", "reports", "users", "settings",
            )
            missing_routes = [route for route in expected_routes if route not in window.navigation]
            if missing_routes:
                raise RuntimeError(f"The GUI is missing routes: {', '.join(missing_routes)}")
            dashboard = window.routes["dashboard"]
            if dashboard.kpi_grid.count() != 4:
                raise RuntimeError("The dashboard did not render all four KPI cards.")
            if dashboard.current_sale.products_scroll.horizontalScrollBar().maximum() != 0:
                raise RuntimeError("The dashboard catalogue overflows horizontally.")
            products_nav = window.navigation["products"]
            products_nav.setFocus()
            QTest.keyClick(products_nav, Qt.Key.Key_Space)
            application.processEvents()
            products = window.routes["products"]
            if not hasattr(products, "table"):
                raise RuntimeError("The products route did not create the catalogue table.")
            if products.table.rowCount() < 1:
                raise RuntimeError("The products route did not load seeded catalogue items.")

            held_item = context.catalog.search_items("Laptop", limit=1)[0]
            laptop_row = next(
                row for row in range(products.table.rowCount())
                if products.table.item(row, 0).text() == str(held_item["name"])
            )
            assert_table_actions_fit(products.table, laptop_row, 6)
            if products.table.horizontalScrollBar().maximum() != 0:
                raise RuntimeError("The Products table overflows at the current display scale.")
            context.sales.hold_sale(
                [{"item_id": int(held_item["id"]), "quantity_milli": 1000}],
                note="Refresh check",
            )
            orders_nav = window.navigation["orders"]
            orders_nav.setFocus()
            QTest.keyClick(orders_nav, Qt.Key.Key_Space)
            application.processEvents()
            orders = window.routes["orders"]
            orders.refresh()
            application.processEvents()
            visible_recall_buttons = [
                button for button in orders.findChildren(QPushButton)
                if button.text() == "Recall" and button.isVisible()
            ]
            if len(visible_recall_buttons) != 1:
                raise RuntimeError("Refreshing Orders left a duplicate or hidden Recall action.")
            if visible_recall_buttons[0].width() > 200:
                raise RuntimeError("The Orders Recall action stretched across its table column.")

            sales_nav = window.navigation["sales"]
            sales_nav.setFocus()
            QTest.keyClick(sales_nav, Qt.Key.Key_Space)
            application.processEvents()
            sale_view = window.routes["sales"]
            if not isinstance(sale_view, CurrentSaleView):
                raise RuntimeError("The sales route did not create the current-sale view.")
            QTest.keyClick(window, Qt.Key.Key_F2)
            if QApplication.focusWidget() is not sale_view.search:
                raise RuntimeError("F2 did not focus the catalogue search.")
            QTest.keyClicks(sale_view.search, "Laptop")
            application.processEvents()
            image_source = Path(directory) / "smoke-laptop.png"
            sample_image = QImage(32, 32, QImage.Format.Format_RGB32)
            sample_image.fill(QColor(DEFAULT_PALETTE.primary))
            if not sample_image.save(str(image_source)):
                raise RuntimeError("Could not create the local product-image test fixture.")
            laptop = context.catalog.search_items("Laptop", limit=1)[0]
            context.catalog.set_item_image(int(laptop["id"]), image_source)
            application.processEvents()
            cards = sale_view.products_page.findChildren(ProductCard)
            if not cards:
                raise RuntimeError("The seeded Laptop product was not found in the catalogue.")
            laptop_card = next(
                (card for card in reversed(cards)
                 if card.item_id == int(laptop["id"]) and card.isVisible()),
                None,
            )
            if laptop_card is None:
                raise RuntimeError("The refreshed catalogue did not include the imaged Laptop.")
            thumbnail = laptop_card.findChild(QLabel, "productThumbnail")
            thumbnail_pixmap = thumbnail.pixmap() if thumbnail is not None else None
            tile_size = thumbnail_pixmap.deviceIndependentSize() if thumbnail_pixmap else None
            if (
                thumbnail_pixmap is None or thumbnail_pixmap.isNull()
                or thumbnail.hasScaledContents()
                or tile_size.width() != thumbnail.width()
                or tile_size.height() != thumbnail.height()
                or abs(tile_size.width() / tile_size.height() - PRODUCT_TILE_RATIO) > 1 / tile_size.height()
            ):
                raise RuntimeError("The saved product image does not fill a uniform 4:5 tile.")
            tile_image = thumbnail_pixmap.toImage()
            if any(
                tile_image.pixelColor(x, y).alpha() != 255
                for y in range(tile_image.height())
                for x in range(tile_image.width())
            ):
                raise RuntimeError("The product tile contains transparent image bands.")
            if any(
                tile_image.pixelColor(x, y) != QColor(DEFAULT_PALETTE.primary)
                for y in range(tile_image.height())
                for x in range(tile_image.width())
            ):
                raise RuntimeError("The solid image fixture was not rendered as a solid fill.")
            add_button = cards[0].findChild(QToolButton)
            if add_button is None:
                raise RuntimeError("The catalogue card has no accessible add button.")
            add_button.setFocus()
            QTest.keyClick(add_button, Qt.Key.Key_Space)
            application.processEvents()
            if len(sale_view.cart) != 1 or sale_view.quote is None:
                raise RuntimeError("Adding the product did not create a service-quoted cart.")
            if not laptop_card.property("selected"):
                raise RuntimeError("The selected sale item did not receive its green outline state.")

            state = {"complete": False, "receipt_preview": False, "error": ""}
            deadline = time.monotonic() + 8

            def dismiss_receipt() -> None:
                active = QApplication.activeModalWidget()
                if isinstance(active, SaleCompleteDialog):
                    state["receipt_preview"] = active.isVisible()
                    done = next(
                        (button for button in active.findChildren(QPushButton)
                         if button.text() == "Done"),
                        None,
                    )
                    if done is None:
                        state["error"] = "Receipt preview has no keyboard-accessible Done action."
                        active.reject()
                        return
                    if not done.isEnabled():
                        if time.monotonic() < deadline:
                            QTimer.singleShot(30, dismiss_receipt)
                            return
                        state["error"] = "Receipt generation did not finish before the GUI smoke timeout."
                        active.reject()
                        return
                    pdf_path = Path(directory) / "smoke-receipt.pdf"
                    active._write_pdf(pdf_path)
                    if not pdf_path.is_file() or not pdf_path.read_bytes().startswith(b"%PDF-"):
                        state["error"] = "The generated receipt PDF is missing or invalid."
                        active.reject()
                        return
                    text_path = context.receipts.export_text(
                        active.sale.id, Path(directory) / "smoke-receipt.txt",
                    )
                    if active.sale.receipt_number not in text_path.read_text(encoding="utf-8"):
                        state["error"] = "The saved text receipt is missing its receipt number."
                        active.reject()
                        return
                    done.setFocus()
                    QTest.keyClick(done, Qt.Key.Key_Space)
                elif time.monotonic() < deadline:
                    QTimer.singleShot(30, dismiss_receipt)

            def send_payment() -> None:
                active = QApplication.activeModalWidget()
                if not isinstance(active, PaymentDialog):
                    state["error"] = "The checkout dialog was not active for payment."
                    return
                thumbnails = active.findChildren(QLabel, "productThumbnail")
                if not thumbnails or thumbnails[0].pixmap() is None or thumbnails[0].pixmap().isNull():
                    state["error"] = "The payment dialog did not display the product image."
                    active.reject()
                    return
                state["payment_attempted"] = True
                QTest.keyClick(
                    QApplication.focusWidget() or active,
                    Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier,
                )
                state["complete"] = active.result() == PaymentDialog.DialogCode.Accepted
                if not state["complete"]:
                    state["error"] = active.error_label.text() or "Ctrl+Enter did not complete payment."
                    active.reject()

            def drive_dialog() -> None:
                active = QApplication.activeModalWidget()
                if isinstance(active, PaymentDialog):
                    QTimer.singleShot(100, dismiss_receipt)
                    QTimer.singleShot(100, send_payment)
                elif time.monotonic() >= deadline:
                    state["error"] = "Timed out waiting for the checkout dialog."
                    return
                else:
                    QTimer.singleShot(30, drive_dialog)

            QTimer.singleShot(0, drive_dialog)
            sale_view.pay_button.setFocus()
            QTest.keyClick(sale_view.pay_button, Qt.Key.Key_Space)
            application.processEvents()
            if state["error"]:
                raise RuntimeError(state["error"])
            if not state["complete"]:
                raise RuntimeError("Keyboard checkout did not complete.")
            if not state["receipt_preview"]:
                raise RuntimeError("The successful-sale receipt preview did not open.")
            if len(context.sales.list_sales(limit=1)) != 1:
                raise RuntimeError("Checkout did not persist a sale.")
            item = context.catalog.search_items("Laptop", limit=1)[0]
            if int(item["stock_milli"]) != 9000:
                raise RuntimeError("Checkout did not reduce one unit of Laptop stock.")
            if len(sale_view.cart) != 0:
                raise RuntimeError("The completed sale cart was not cleared.")
            history = window.routes["sales_history"]
            window.navigation["sales_history"].click()
            application.processEvents()
            if history.table.rowCount() != 1:
                raise RuntimeError("Sales history did not refresh after checkout.")
            assert_table_actions_fit(history.table, 0, 6)
            if history.table.horizontalScrollBar().maximum() != 0:
                raise RuntimeError("The Sales History table overflows at the current display scale.")
            receipt = ReceiptWidget(context.receipts, int(history._sales[0]["id"]))
            quantity_lines = [
                label.text() for label in receipt.findChildren(QLabel)
                if " x " in label.text()
            ]
            if not any(line.startswith("1 x ") for line in quantity_lines):
                raise RuntimeError("The receipt quantity still shows trailing decimals.")
            reports = window.routes["reports"]
            reports.start.setText(date.today().replace(day=1).isoformat())
            reports.end.setText(date.today().isoformat())
            window.navigation["reports"].click()
            application.processEvents()
            if reports.kpi_grid.count() != 4 or len(reports.chart.series) != 1:
                raise RuntimeError("The operational report did not refresh after checkout.")
            selected_day = date.today()
            expected_week_start = selected_day - timedelta(days=selected_day.weekday())
            reports.start.setText(selected_day.isoformat())
            reports.period.setCurrentIndex(reports.period.findData("weekly"))
            application.processEvents()
            if reports.end.text() != (expected_week_start + timedelta(days=6)).isoformat():
                raise RuntimeError("The weekly report did not show the selected week's end date.")
            if reports.end.isEnabled():
                raise RuntimeError("The weekly report allowed manual editing of its calculated end date.")
            bounds = reports._bounds()
            if bounds[0] != expected_week_start or (bounds[2] - bounds[1]).days != 7:
                raise RuntimeError("The weekly report did not cover Monday through Sunday.")
            reports.refresh()
            if len(reports.chart.series) != 1:
                raise RuntimeError("The weekly report did not include this week's completed sale.")
            settings = window.routes["settings"]
            if not settings.payment_checks["Bank transfer"].isChecked():
                raise RuntimeError("Settings does not reflect the configured Bank transfer method.")
            if not any(
                button.text() == "My profile"
                for button in window.findChildren(QPushButton)
            ):
                raise RuntimeError("The administrator has no self-service profile action.")

            def save_profile() -> None:
                active = QApplication.activeModalWidget()
                if not isinstance(active, ProfileDialog):
                    return
                active.username.setText("admin-updated")
                active.display_name.setText("Updated Administrator")
                active.current_password.setText("smoke-password-new")
                active.new_password.setText("profile-password-new")
                active.confirm_password.setText("profile-password-new")
                active._save()

            QTimer.singleShot(0, save_profile)
            window._edit_profile()
            updated_user = context.auth.current_user
            if updated_user is None or updated_user.username != "admin-updated":
                raise RuntimeError("The profile dialog did not save the new username.")
            if updated_user.display_name != "Updated Administrator":
                raise RuntimeError("The profile dialog did not save the new display name.")
            if window.user_name_label.text() != updated_user.display_name:
                raise RuntimeError("The shell did not refresh the administrator's name.")
            if window.welcome_title.text() != "Welcome back, Updated Administrator!":
                raise RuntimeError("The welcome heading did not refresh after profile changes.")
            print("Keyboard-only Qt checkout, payment, stock reduction, and receipt passed.")
            window.close()
            bridge.unsubscribe()
            return 0
        finally:
            if bridge is not None:
                bridge.unsubscribe()
            if application is not None:
                application.processEvents()
            context.close()


if __name__ == "__main__":
    raise SystemExit(main())
