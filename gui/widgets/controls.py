"""Reusable service-oriented Qt widgets for the POS interface."""

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QGuiApplication, QImageReader, QPainter, QPainterPath,
    QPixmap, QResizeEvent,
)
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget, QHeaderView,
)

from backend.core.money import fmt, fmt_qty
from backend.services.support import ReceiptService
from gui.icons import load_icon
from gui.styles.tokens import DEFAULT_PALETTE, Palette, px
from gui.i18n import t

PRODUCT_TILE_RATIO = 4 / 5


def apply_card_elevation(widget: QWidget) -> None:
    """Give important card surfaces a restrained, scalable lift."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(px(20))
    shadow.setOffset(0, px(3))
    shadow.setColor(QColor(30, 41, 59, 18))
    widget.setGraphicsEffect(shadow)


def fit_pixmap(image: QPixmap, width: int, height: int) -> QPixmap:
    """Fit a complete image inside a target size without cropping or distortion."""
    width = max(1, int(width))
    height = max(1, int(height))
    if image.isNull():
        return QPixmap()

    device_ratio = _device_pixel_ratio()
    pixel_width = max(1, round(width * device_ratio))
    pixel_height = max(1, round(height * device_ratio))
    fitted = image.scaled(
        QSize(pixel_width, pixel_height),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QPixmap(pixel_width, pixel_height)
    canvas.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(canvas)
    painter.drawPixmap(
        (pixel_width - fitted.width()) // 2,
        (pixel_height - fitted.height()) // 2,
        fitted,
    )
    painter.end()
    canvas.setDevicePixelRatio(device_ratio)
    return canvas


def cover_pixmap(
    image: QPixmap, width: int, height: int, focus_y: float = 0.4,
) -> QPixmap:
    """Scale and crop an image to cover a DPR-aware target without distortion."""
    width = max(1, int(width))
    height = max(1, int(height))
    if not 0 <= focus_y <= 1:
        raise ValueError("Vertical image focus must be between zero and one.")
    if image.isNull():
        return QPixmap()

    device_ratio = _device_pixel_ratio()
    return _cover_pixmap_pixels(
        image, max(1, round(width * device_ratio)),
        max(1, round(height * device_ratio)), focus_y, device_ratio,
    )


def load_product_pixmap(image_path: str | Path) -> QPixmap:
    """Load a local product image with EXIF orientation and an mtime cache."""
    path = Path(image_path)
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        return QPixmap()
    return _load_product_pixmap_cached(str(path.resolve()), modified_ns)


def product_thumbnail_pixmap(
    image_path: str | Path, width: int, height: int,
) -> QPixmap:
    """Return a cached cover-cropped local image for the requested tile size."""
    width = max(1, int(width))
    height = max(1, int(height))
    path = Path(image_path)
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        return QPixmap()
    device_ratio = _device_pixel_ratio()
    pixel_width = max(1, round(width * device_ratio))
    pixel_height = max(1, round(height * device_ratio))
    return _product_thumbnail_cached(
        str(path.resolve()), modified_ns, pixel_width, pixel_height, device_ratio,
    )


def _device_pixel_ratio() -> float:
    """Return the primary screen DPR, or one when Qt has no active screen."""
    application = QGuiApplication.instance()
    screen = application.primaryScreen() if application is not None else None
    return screen.devicePixelRatio() if screen is not None else 1.0


@lru_cache(maxsize=256)
def _load_product_pixmap_cached(path: str, modified_ns: int) -> QPixmap:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


@lru_cache(maxsize=1024)
def _product_thumbnail_cached(
    path: str, modified_ns: int, width: int, height: int, device_ratio: float,
) -> QPixmap:
    image = _load_product_pixmap_cached(path, modified_ns)
    if image.isNull():
        return QPixmap()
    return _cover_pixmap_pixels(image, width, height, 0.4, device_ratio)


def _cover_pixmap_pixels(
    image: QPixmap, width: int, height: int, focus_y: float, device_ratio: float,
) -> QPixmap:
    source = QPixmap(image)
    source.setDevicePixelRatio(1.0)
    scaled = source.scaled(
        QSize(width, height),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    overflow_x = max(0, scaled.width() - width)
    overflow_y = max(0, scaled.height() - height)
    source_rect = QRectF(
        overflow_x / 2,
        round(overflow_y * focus_y),
        width,
        height,
    )
    canvas = QPixmap(width, height)
    canvas.fill(QColor(DEFAULT_PALETTE.card))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(QRectF(0, 0, width, height), scaled, source_rect)
    painter.end()
    canvas.setDevicePixelRatio(device_ratio)
    return canvas


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
    fit_table_to_viewport(table, protected_columns=(column,))


def fit_table_to_viewport(table: Any, protected_columns: Sequence[int] = ()) -> None:
    """Keep every table column visible, whatever font metrics are in use.

    Action columns hold real buttons, so their width is preserved. The other
    columns are scaled to the viewport; long text is elided by Qt instead of
    forcing a horizontal scrollbar.
    """
    header = table.horizontalHeader()
    protected = set(protected_columns)
    flexible = [
        column for column in range(table.columnCount()) if column not in protected
    ]
    if not flexible:
        return
    reserved = sum(table.columnWidth(column) for column in protected)
    available = max(px(120), table.viewport().width() - reserved)
    widths = [table.columnWidth(column) for column in flexible]
    total = sum(widths)
    if total <= 0:
        return
    if total > available:
        minimum = px(56)
        widths = [max(minimum, int(width * available / total)) for width in widths]
    else:
        extra = (available - total) // len(flexible)
        widths = [width + extra for width in widths]
    for column, width in zip(flexible, widths):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(column, width)


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


class ElidedLabel(QLabel):
    """Show one line of text, eliding its end to the current label width."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setWordWrap(False)
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        self.setText(self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, max(0, self.width()),
        ))


class _ProductThumbnail(QLabel):
    """Paint a cover-cropped image with rounded top corners or a fallback initial."""

    def __init__(
        self, aspect_ratio: float, palette: Palette = DEFAULT_PALETTE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.aspect_ratio = aspect_ratio
        self._palette = palette
        self.image_path = ""
        self._fallback_text = ""
        self.setObjectName("productThumbnail")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_image_path(self, image_path: str, fallback_text: str) -> None:
        """Set a local image source and a first-letter fallback."""
        self.image_path = image_path
        self._fallback_text = fallback_text[:1].upper()
        self._refresh_pixmap()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = float(px(12))
        width = float(self.width())
        height = float(self.height())
        clip = QPainterPath()
        clip.moveTo(0, height)
        clip.lineTo(0, radius)
        clip.quadTo(0, 0, radius, 0)
        clip.lineTo(width - radius, 0)
        clip.quadTo(width, 0, width, radius)
        clip.lineTo(width, height)
        clip.closeSubpath()
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), QColor(self._palette.tint))
        pixmap = self.pixmap()
        if pixmap is not None and not pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(self.rect(), pixmap)
        else:
            painter.setPen(QColor(self._palette.primary_text or self._palette.primary))
            font = self.font()
            font.setPixelSize(min(px(38), max(px(18), round(min(width, height) * 0.2))))
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._fallback_text)

    def _refresh_pixmap(self) -> None:
        if not self.image_path or self.width() <= 0 or self.height() <= 0:
            self.setPixmap(QPixmap())
            self.update()
            return
        pixmap = product_thumbnail_pixmap(
            self.image_path, self.width(), self.height(),
        )
        self.setPixmap(pixmap)
        self.update()


def make_thumbnail_label(
    image_path: str, name: str, size: int = 48,
    parent: QWidget | None = None, palette: Palette = DEFAULT_PALETTE,
) -> QLabel:
    """Create a square cover-cropped thumbnail with a tinted initial fallback."""
    thumbnail = _ProductThumbnail(1.0, palette, parent)
    thumbnail.setFixedSize(px(size), px(size))
    thumbnail.set_image_path(image_path, name)
    return thumbnail


class ProductCard(QFrame):
    """Show one catalogue item and emit a request to add it to a sale."""

    add_requested = Signal(int)

    def __init__(
        self, item: Mapping[str, Any], currency: str,
        parent: QWidget | None = None, palette: Palette = DEFAULT_PALETTE,
    ) -> None:
        super().__init__(parent)
        self.item_id = int(item["id"])
        self.setProperty("productCard", True)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(px(180))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        thumbnail = _ProductThumbnail(PRODUCT_TILE_RATIO, palette)
        image_path = str(item.get("image_path") or "")
        thumbnail.set_image_path(image_path, str(item["name"]))
        layout.addWidget(thumbnail)
        details = QWidget()
        details.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(px(10), px(8), px(10), px(9))
        details_layout.setSpacing(px(3))
        name = ElidedLabel(str(item["name"]))
        name.setObjectName("productName")
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
        stock_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(px(6))
        price = QLabel(fmt(int(item["price_minor"]), currency))
        price.setObjectName("productPrice")
        add_button = QToolButton()
        add_button.setFixedSize(px(30), px(30))
        add_button.setToolTip(t("add_to_sale", "Add to sale"))
        add_button.setAccessibleName(t("add_to_sale", "Add to sale"))
        add_button.setIcon(load_icon("plus", palette.on_primary, px(14)))
        add_button.setProperty("primary", True)
        add_button.clicked.connect(lambda: self.add_requested.emit(self.item_id))
        footer.addWidget(price, 1)
        footer.addWidget(add_button)
        details_layout.addWidget(name)
        details_layout.addWidget(stock_label)
        details_layout.addLayout(footer)
        layout.addWidget(details)
        self._thumbnail = thumbnail
        self._details = details

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        tile_width = max(1, self._thumbnail.width())
        tile_height = max(1, round(tile_width / PRODUCT_TILE_RATIO))
        if self._thumbnail.height() != tile_height:
            self._thumbnail.setFixedHeight(tile_height)
        card_height = tile_height + self._details.sizeHint().height() + 2
        if self.height() != card_height:
            self.setFixedHeight(card_height)


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
        icon_color = palette.primary
        self.decrease_button.setIcon(load_icon("minus", icon_color, 14))
        self.increase_button.setIcon(load_icon("plus", icon_color, 14))
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
        self.value_label.setText(fmt_qty(self._quantity_milli))


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
        layout.setContentsMargins(px(2), px(6), px(2), px(6))
        layout.setSpacing(px(6))
        thumbnail = make_thumbnail_label(
            str(line.get("image_path") or ""), str(line["name"]), 44,
            parent=self, palette=palette,
        )
        detail = QVBoxLayout()
        name = QLabel(str(line["name"]))
        name.setObjectName("cartItemName")
        name.setWordWrap(False)
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
        layout.addWidget(thumbnail)
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
            quantity = fmt_qty(int(item["quantity_milli"]))
            unit_price = fmt(int(item["unit_price_minor"]), receipt["currency"])
            detail.addWidget(QLabel(f"{quantity} x {unit_price}"), 1)
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
