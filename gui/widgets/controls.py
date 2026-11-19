"""Reusable service-oriented Qt widgets for the POS interface."""

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QToolButton, QVBoxLayout, QWidget, QHeaderView,
)

from backend.core.money import fmt, milli_to_qty
from backend.services.support import ReceiptService
from gui.icons import load_icon
from gui.styles.tokens import DEFAULT_PALETTE, Palette, px
from gui.i18n import t


def apply_card_elevation(widget: QWidget) -> None:
    """Give important card surfaces a restrained, scalable lift."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(px(20))
    shadow.setOffset(0, px(3))
    shadow.setColor(QColor(30, 41, 59, 18))
    widget.setGraphicsEffect(shadow)


def configure_table(table: Any) -> None:
    """Apply the shared readable table row, selection, and header behavior."""
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setMinimumSectionSize(px(46))
    table.verticalHeader().setDefaultSectionSize(px(54))
    table.horizontalHeader().setMinimumHeight(px(42))
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)

def clear_table_widgets(table: Any) -> None:
    """Hide and retire embedded controls before refreshing a table's rows."""
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            widget = table.cellWidget(row, column)
            if widget is not None:
                table.removeCellWidget(row, column)
                widget.hide()
                widget.deleteLater()
    table.clearContents()


def set_table_action_cell(table: Any, row: int, column: int, widget: QWidget) -> None:
    """Set an embedded action cell in a table row."""
    table.setCellWidget(row, column, widget)


def fit_table_action_column(table: Any, column: int) -> None:
    """Keep an action column wide enough for the largest row of controls."""
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
    content_width = max(
        (
            widget.sizeHint().width()
            for row in range(table.rowCount())
            if (widget := table.cellWidget(row, column)) is not None
        ),
        default=0,
    )
    if content_width:
        table.setColumnWidth(
            column, max(table.columnWidth(column), content_width + px(36))
        )


class SidebarNavItem(QPushButton):
    """Navigation button that exposes a route key to its owning shell."""

    navigation_requested = Signal(str)

    def __init__(
        self, route: str, label: str, icon_name: str, parent: QWidget | None = None,
        palette: Palette = DEFAULT_PALETTE,
    ) -> None:
        super().__init__(label, parent)
        self.route = route
        self.icon_name = icon_name
        self.palette = palette
        self.setIcon(load_icon(icon_name, palette.on_primary, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.clicked.connect(lambda: self.navigation_requested.emit(self.route))

    def set_active(self, active: bool) -> None:
        """Set the active route state for stylesheet selectors."""
        self.setProperty("active", active)
        self.setChecked(active)
        icon_color = self.palette.primary if active else self.palette.on_primary
        self.setIcon(load_icon(self.icon_name, icon_color, 18))
        self.style().unpolish(self)
        self.style().polish(self)


class KpiCard(QFrame):
    """Display a service-provided dashboard metric and comparison label."""

    def __init__(
        self, title: str, value: str, delta: str = "", parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        apply_card_elevation(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(18), px(16), px(18), px(16))
        layout.setSpacing(px(8))
        self.title_label = QLabel(title)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("kpiValue")
        self.delta_label = QLabel(delta)
        self.delta_label.setObjectName("kpiDelta")
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.delta_label)

    def set_value(self, value: str, delta: str = "") -> None:
        """Refresh the card from a new dashboard response."""
        self.value_label.setText(value)
        self.delta_label.setText(delta)


class ProductCard(QFrame):
    """Show one catalogue item and emit a request to add it to a sale."""

    add_requested = Signal(int)

    def __init__(
        self, item: Mapping[str, Any], currency: str,
        parent: QWidget | None = None, palette: Palette = DEFAULT_PALETTE,
    ) -> None:
        super().__init__(parent)
        self.item_id = int(item["id"])
        self.setProperty("card", True)
        self.setProperty("productCard", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(px(220))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(12), px(12), px(12), px(12))
        layout.setSpacing(px(7))
        thumbnail = QLabel()
        thumbnail.setObjectName("productThumbnail")
        thumbnail.setFixedHeight(px(78))
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_path = str(item.get("image_path") or "")
        image = QPixmap(image_path) if image_path else QPixmap()
        if not image.isNull():
            thumbnail.setPixmap(image.scaled(
                px(150), px(78), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            thumbnail.setText(str(item["name"])[:1].upper())
        layout.addWidget(thumbnail)
        name = QLabel(str(item["name"]))
        name.setObjectName("productName")
        name.setWordWrap(False)
        name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        stock = int(item.get("stock_milli", 0))
        item_type = str(item.get("item_type", "product"))
        stock_text = (
            t("available", "Available") if item_type in {"service", "non_inventory"}
            else t("out_of_stock", "Out of stock") if stock == 0
            else t("low_stock", "Low stock") if item.get("low_stock_milli", 0) >= stock
            else t("in_stock", "In stock")
        )
        stock_label = QLabel(stock_text)
        stock_label.setObjectName("stockStatus")
        footer = QHBoxLayout()
        price = QLabel(fmt(int(item["price_minor"]), currency))
        price.setObjectName("productPrice")
        add_button = QToolButton()
        add_button.setToolTip(t("add_to_sale", "Add to sale"))
        add_button.setAccessibleName(t("add_to_sale", "Add to sale"))
        add_button.setIcon(load_icon("plus", palette.on_primary, 16))
        add_button.setProperty("primary", True)
        add_button.clicked.connect(lambda: self.add_requested.emit(self.item_id))
        footer.addWidget(price, 1)
        footer.addWidget(add_button)
        layout.addWidget(name)
        layout.addWidget(stock_label)
        layout.addLayout(footer)


class CategoryChip(QPushButton):
    """Checkable category filter chip."""

    category_selected = Signal(str)

    def __init__(self, key: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.category_key = key
        self.setProperty("categoryChip", True)
        self.setCheckable(True)
        self.clicked.connect(lambda: self.category_selected.emit(self.category_key))


class QuantityStepper(QWidget):
    """Adjust a nonnegative integer-thousandth quantity."""

    quantity_changed = Signal(int)

    def __init__(
        self, quantity_milli: int = 1000, step_milli: int = 1000,
        parent: QWidget | None = None, palette: Palette = DEFAULT_PALETTE,
    ) -> None:
        super().__init__(parent)
        if quantity_milli < 0 or step_milli <= 0:
            raise ValueError("Quantity must be nonnegative and step must be positive.")
        self._quantity_milli = quantity_milli
        self._step_milli = step_milli
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(px(6))
        self.decrease_button = QToolButton()
        self.increase_button = QToolButton()
        self.decrease_button.setToolTip(t("decrease_quantity", "Decrease quantity"))
        self.increase_button.setToolTip(t("increase_quantity", "Increase quantity"))
        self.decrease_button.setIcon(load_icon("minus", palette.secondary, 14))
        self.increase_button.setIcon(load_icon("plus", palette.secondary, 14))
        self.value_label = QLabel()
        self.value_label.setMinimumWidth(px(42))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.decrease_button.clicked.connect(lambda: self.set_quantity(max(0, self._quantity_milli - self._step_milli)))
        self.increase_button.clicked.connect(lambda: self.set_quantity(self._quantity_milli + self._step_milli))
        layout.addWidget(self.decrease_button)
        layout.addWidget(self.value_label)
        layout.addWidget(self.increase_button)
        self._refresh()

    @property
    def quantity_milli(self) -> int:
        """Return the exact current quantity."""
        return self._quantity_milli

    def set_quantity(self, quantity_milli: int) -> None:
        """Set quantity and emit only when the value changes."""
        if quantity_milli < 0:
            raise ValueError("Quantity cannot be negative.")
        if self._quantity_milli == quantity_milli:
            return
        self._quantity_milli = quantity_milli
        self._refresh()
        self.quantity_changed.emit(quantity_milli)

    def _refresh(self) -> None:
        quantity = milli_to_qty(self._quantity_milli).normalize()
        self.value_label.setText(f"{quantity:f}")


class CartLineItem(QFrame):
    """Display a quoted sale line and emit quantity/removal intents."""

    quantity_changed = Signal(int, int)
    remove_requested = Signal(int)

    def __init__(
        self, line: Mapping[str, Any], currency: str,
        parent: QWidget | None = None, palette: Palette = DEFAULT_PALETTE,
    ) -> None:
        super().__init__(parent)
        self.item_id = int(line["item_id"])
        self.setProperty("cartLine", True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(px(4), px(8), px(4), px(8))
        layout.setSpacing(px(10))
        detail = QVBoxLayout()
        name = QLabel(str(line["name"]))
        name.setObjectName("cartItemName")
        detail.addWidget(name)
        detail.addWidget(QLabel(fmt(int(line["unit_price_minor"]), currency)))
        stepper = QuantityStepper(
            int(line["quantity_milli"]),
            step_milli=250 if line.get("item_type") == "weighed" else 1000,
            parent=self,
            palette=palette,
        )
        stepper.quantity_changed.connect(
            lambda value: self.quantity_changed.emit(self.item_id, value)
        )
        total = QLabel(fmt(int(line["line_total_minor"]), currency))
        total.setObjectName("cartLineTotal")
        remove_button = QToolButton()
        remove_button.setToolTip(t("remove_item", "Remove item"))
        remove_button.setAccessibleName(t("remove_item", "Remove item"))
        remove_button.setIcon(load_icon("close", palette.muted, 16))
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self.item_id))
        layout.addLayout(detail, 1)
        layout.addWidget(stepper)
        layout.addWidget(total)
        layout.addWidget(remove_button)


class StatusPill(QLabel):
    """Compact semantic status label."""

    def __init__(self, status: str, parent: QWidget | None = None) -> None:
        super().__init__(status, parent)
        self.setObjectName("statusPill")
        self.setProperty("status", status.casefold())


class SearchField(QLineEdit):
    """Search field with separate live-query and submitted-query signals."""

    search_submitted = Signal(str)

    def __init__(self, placeholder: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder or t("search", "Search"))
        self.setClearButtonEnabled(True)
        self.returnPressed.connect(lambda: self.search_submitted.emit(self.text().strip()))


class Toast(QLabel):
    """Nonmodal, timed message anchored to the bottom-right of its parent."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, message: str, duration_ms: int = 2600) -> None:
        """Show a short status message without blocking the interface."""
        if duration_ms <= 0:
            raise ValueError("Toast duration must be positive.")
        self.setText(message)
        self.adjustSize()
        margin = px(24)
        self.move(max(margin, self.parentWidget().width() - self.width() - margin),
                  max(margin, self.parentWidget().height() - self.height() - margin))
        self.raise_()
        self.show()
        self._timer.start(duration_ms)


class SideDrawer(QFrame):
    """A hideable side panel with an explicit close signal."""

    close_requested = Signal()

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        apply_card_elevation(self)
        self.setFixedWidth(px(420))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(20), px(18), px(20), px(18))
        heading = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("drawerTitle")
        close_button = QToolButton()
        close_button.setToolTip(t("close", "Close"))
        close_button.setAccessibleName(t("close", "Close"))
        close_button.setIcon(load_icon("close", DEFAULT_PALETTE.secondary, 18))
        close_button.clicked.connect(self.close_drawer)
        heading.addWidget(self.title_label, 1)
        heading.addWidget(close_button)
        layout.addLayout(heading)
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout, 1)
        self.hide()

    def open(self) -> None:
        """Show the drawer and move focus to its first control."""
        self.show()
        self.raise_()

    def close_drawer(self) -> None:
        """Hide the drawer and emit its close signal."""
        self.hide()
        self.close_requested.emit()


class ReceiptWidget(QFrame):
    """Render a persisted receipt using the receipt service's saved snapshots."""

    def __init__(
        self, receipt_service: ReceiptService, sale_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("receiptPaper", True)
        self.setFixedWidth(px(390))
        receipt = receipt_service.build_receipt(sale_id)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(22), px(18), px(22), px(18))
        layout.setSpacing(px(7))
        heading = QLabel(receipt["business_name"])
        heading.setObjectName("receiptBusiness")
        layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignHCenter)
        number = QLabel(receipt["sale"]["receipt_number"])
        layout.addWidget(number, alignment=Qt.AlignmentFlag.AlignHCenter)
        created_at = QLabel(str(receipt["sale"]["created_at"]).replace("T", " "))
        created_at.setObjectName("mutedText")
        layout.addWidget(created_at, alignment=Qt.AlignmentFlag.AlignHCenter)
        customer = receipt["customer"]
        if customer:
            customer_label = QLabel(f"{t('customer', 'Customer')}: {customer['name']}")
            customer_label.setWordWrap(True)
            layout.addWidget(customer_label)
        separator = QFrame()
        separator.setObjectName("receiptSeparator")
        separator.setFixedHeight(px(1))
        layout.addWidget(separator)
        for item in receipt["items"]:
            name = QLabel(str(item["name_snapshot"]))
            name.setWordWrap(True)
            layout.addWidget(name)
            detail = QHBoxLayout()
            quantity = milli_to_qty(int(item["quantity_milli"])).normalize()
            unit_price = fmt(int(item["unit_price_minor"]), receipt["currency"])
            detail.addWidget(QLabel(f"{quantity:f} x {unit_price}"), 1)
            detail.addWidget(QLabel(fmt(int(item["line_total_minor"]), receipt["currency"])))
            layout.addLayout(detail)
        separator = QFrame()
        separator.setObjectName("receiptSeparator")
        separator.setFixedHeight(px(1))
        layout.addWidget(separator)
        for key, label in (
            ("subtotal_minor", t("subtotal", "Subtotal")),
            ("discount_minor", t("discount", "Discount")),
            ("tax_minor", t("tax", "Tax")),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            row.addWidget(QLabel(fmt(int(receipt["sale"][key]), receipt["currency"])))
            layout.addLayout(row)
        total = QLabel(fmt(int(receipt["sale"]["total_minor"]), receipt["currency"]))
        total.setObjectName("receiptTotal")
        layout.addWidget(total, alignment=Qt.AlignmentFlag.AlignRight)
        payment_heading = QLabel(t("payment_method", "Payment"))
        payment_heading.setObjectName("sectionTitle")
        layout.addWidget(payment_heading)
        for payment in receipt["payments"]:
            row = QHBoxLayout()
            row.addWidget(QLabel(str(payment["method"]),), 1)
            row.addWidget(QLabel(fmt(int(payment["amount_minor"]), receipt["currency"])))
            layout.addLayout(row)
        change_minor = int(receipt["sale"]["change_minor"])
        if change_minor:
            row = QHBoxLayout()
            row.addWidget(QLabel(t("change_due", "Change due")), 1)
            row.addWidget(QLabel(fmt(change_minor, receipt["currency"])))
            layout.addLayout(row)
        thank_you = QLabel(t("receipt_thank_you", "Thank you for shopping with us"))
        thank_you.setObjectName("mutedText")
        layout.addWidget(thank_you, alignment=Qt.AlignmentFlag.AlignHCenter)


class ModuleToggleRow(QFrame):
    """Settings row that emits a module key and enabled state."""

    module_changed = Signal(str, bool)

    def __init__(
        self, module_key: str, label: str, enabled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.module_key = module_key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(px(12), px(9), px(12), px(9))
        layout.addWidget(QLabel(label), 1)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(enabled)
        self.checkbox.toggled.connect(
            lambda value: self.module_changed.emit(self.module_key, value)
        )
        layout.addWidget(self.checkbox)
