"""Service-backed catalogue and current-sale workspace."""

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.errors import NotFoundError, PosError
from backend.core.money import fmt
from backend.models.cart import Cart
from backend.models.records import SaleResult
from gui.dialogs.payment import PaymentDialog
from gui.i18n import t
from gui.styles.tokens import px
from gui.widgets import (
    CartLineItem, CategoryChip, ProductCard, SearchField, Toast, apply_card_elevation,
)


class CurrentSaleView(QWidget):
    """Search the catalogue, edit a validated cart, and complete payment."""

    sale_completed = Signal(object)

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.cart = Cart()
        self.quote: dict[str, Any] | None = None
        currency = context.settings.get("currency")
        if not currency:
            raise RuntimeError("The business currency is not configured.")
        self.currency = currency
        self.category_id: int | None = None
        self.toast = Toast(self)
        self._category_chips: list[CategoryChip] = []
        self._product_cards: list[ProductCard] = []
        self._reflow_queued = False

        root = QVBoxLayout(self)
        root.setContentsMargins(px(24), px(22), px(24), px(22))
        root.setSpacing(px(14))
        heading = QLabel(t("current_sale", "Current sale"))
        heading.setObjectName("drawerTitle")
        root.addWidget(heading)

        workspace = QHBoxLayout()
        workspace.setSpacing(px(16))
        root.addLayout(workspace, 1)

        catalogue = QVBoxLayout()
        catalogue.setSpacing(px(12))
        workspace.addLayout(catalogue, 5)
        self.search = SearchField(t(
            "search_items",
            f"Search {t('item', 'items').lower()} by name or barcode",
        ))
        self.search.textChanged.connect(self._search_catalogue)
        self.search.search_submitted.connect(self._submit_search)
        catalogue.addWidget(self.search)
        self.category_row = QHBoxLayout()
        self.category_row.setSpacing(px(8))
        catalogue.addLayout(self.category_row)
        self.products_scroll = QScrollArea()
        self.products_scroll.setWidgetResizable(True)
        self.products_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.products_page = QWidget()
        self.products_grid = QGridLayout(self.products_page)
        self.products_grid.setContentsMargins(0, 0, 0, 0)
        self.products_grid.setSpacing(px(14))
        self.products_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.products_scroll.setWidget(self.products_page)
        catalogue.addWidget(self.products_scroll, 1)

        ticket = QFrame()
        ticket.setProperty("card", True)
        apply_card_elevation(ticket)
        ticket.setMinimumWidth(px(340))
        ticket_layout = QVBoxLayout(ticket)
        ticket_layout.setContentsMargins(px(18), px(16), px(18), px(16))
        ticket_layout.setSpacing(px(12))
        ticket_header = QHBoxLayout()
        ticket_title = QLabel(t("sale_ticket", "Sale ticket"))
        ticket_title.setObjectName("drawerTitle")
        ticket_header.addWidget(ticket_title, 1)
        self.clear_button = QPushButton(t("clear", "Clear"))
        self.clear_button.clicked.connect(self._clear_cart)
        ticket_header.addWidget(self.clear_button)
        ticket_layout.addLayout(ticket_header)
        self.cart_scroll = QScrollArea()
        self.cart_scroll.setWidgetResizable(True)
        self.cart_page = QWidget()
        self.cart_lines_layout = QVBoxLayout(self.cart_page)
        self.cart_lines_layout.setContentsMargins(0, 0, 0, 0)
        self.cart_lines_layout.setSpacing(px(6))
        self.cart_scroll.setWidget(self.cart_page)
        ticket_layout.addWidget(self.cart_scroll, 1)
        self.subtotal_label = QLabel()
        self.tax_label = QLabel()
        self.discount_label = QLabel()
        self.total_label = QLabel()
        self.total_label.setObjectName("receiptTotal")
        for label in (self.subtotal_label, self.tax_label, self.discount_label, self.total_label):
            ticket_layout.addWidget(label)
        self.pay_button = QPushButton(t("take_payment", "Take payment"))
        self.pay_button.setProperty("checkout", True)
        self.pay_button.setEnabled(False)
        self.pay_button.clicked.connect(self._open_payment)
        ticket_layout.addWidget(self.pay_button)
        self.hold_button = QPushButton(t("hold_sale", "Hold sale"))
        self.hold_button.clicked.connect(self.hold_current_sale)
        self.hold_button.setEnabled(False)
        ticket_layout.addWidget(self.hold_button)
        workspace.insertWidget(0, ticket, 4)
        workspace.setStretch(0, 4)
        workspace.setStretch(1, 5)

        self._load_categories()
        self._search_catalogue()
        self._render_cart()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._reflow_queued:
            self._reflow_queued = True
            QTimer.singleShot(0, self._reflow_products)

    def focus_search(self) -> None:
        """Move keyboard focus to the catalogue search box."""
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()

    def _load_categories(self) -> None:
        while self.category_row.count():
            layout_item = self.category_row.takeAt(0)
            widget = layout_item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._category_chips.clear()
        all_chip = CategoryChip("all", t("all_items", "All items"))
        all_chip.setChecked(self.category_id is None)
        all_chip.category_selected.connect(lambda _: self._select_category(None))
        self.category_row.addWidget(all_chip)
        self._category_chips.append(all_chip)
        for category in self.context.catalog.list_categories():
            category_id = int(category["id"])
            chip = CategoryChip(str(category_id), str(category["name"]))
            chip.setChecked(self.category_id == category_id)
            chip.category_selected.connect(
                lambda _, selected_id=category_id: self._select_category(selected_id)
            )
            self.category_row.addWidget(chip)
            self._category_chips.append(chip)
        self.category_row.addStretch(1)

    def refresh_catalog(self) -> None:
        """Refresh catalogue cards and category filters after catalogue changes."""
        self._load_categories()
        self._search_catalogue(self.search.text())

    def _select_category(self, category_id: int | None) -> None:
        self.category_id = category_id
        selected_key = "all" if category_id is None else str(category_id)
        for chip in self._category_chips:
            chip.setChecked(chip.category_key == selected_key)
        self._search_catalogue()

    def _search_catalogue(self, query: str = "") -> None:
        try:
            items = self.context.catalog.search_items(
                query.strip(), category_id=self.category_id, limit=100,
            )
        except PosError as error:
            self.toast.show_message(error.message)
            return
        self._clear_layout(self.products_grid)
        self._product_cards.clear()
        if not items:
            empty = QLabel(t("no_items_found", "No items match this search."))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.products_grid.addWidget(empty, 0, 0)
            return
        selected_ids = {line.item_id for line in self.cart.lines()}
        for index, item in enumerate(items):
            card = ProductCard(item, self.currency)
            card.set_selected(card.item_id in selected_ids)
            card.add_requested.connect(self._add_item)
            self._product_cards.append(card)
        self._reflow_products()

    def _reflow_products(self) -> None:
        """Fit catalogue cards into the current viewport without horizontal overflow."""
        self._reflow_queued = False
        if not self._product_cards:
            return
        viewport_width = self.products_scroll.viewport().width()
        if viewport_width <= 0:
            return
        spacing = max(0, self.products_grid.horizontalSpacing())
        minimum_width = px(190)
        columns = max(2, min(5, (viewport_width + spacing) // (minimum_width + spacing)))
        columns = min(columns, len(self._product_cards))
        for column in range(5):
            self.products_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self._product_cards):
            self.products_grid.removeWidget(card)
            self.products_grid.addWidget(card, index // columns, index % columns)

    def _submit_search(self, query: str) -> None:
        if not query or not self.context.settings.modules().get("barcode", False):
            return
        try:
            item = self.context.catalog.find_by_barcode(query)
        except NotFoundError:
            return
        except PosError as error:
            self.toast.show_message(error.message)
            return
        self._add_item(int(item["id"]))
        self.search.clear()
        self.focus_search()

    def _candidate_cart(self) -> Cart:
        candidate = Cart()
        for line in self.cart.lines():
            candidate.add(line.item_id, line.quantity_milli)
        return candidate

    def _commit_cart(self, candidate: Cart) -> bool:
        quote: dict[str, Any] | None = None
        if len(candidate):
            try:
                quote = self.context.sales.quote_sale(candidate.to_sale_lines())
            except PosError as error:
                self.toast.show_message(error.message)
                return False
        self.cart = candidate
        self.quote = quote
        self._render_cart()
        return True

    def _add_item(self, item_id: int) -> None:
        candidate = self._candidate_cart()
        try:
            candidate.add(item_id)
        except PosError as error:
            self.toast.show_message(error.message)
            return
        self._commit_cart(candidate)

    def _set_quantity(self, item_id: int, quantity_milli: int) -> None:
        candidate = self._candidate_cart()
        try:
            candidate.set_quantity(item_id, quantity_milli)
        except PosError as error:
            self.toast.show_message(error.message)
            return
        self._commit_cart(candidate)

    def _remove_item(self, item_id: int) -> None:
        candidate = self._candidate_cart()
        candidate.remove(item_id)
        self._commit_cart(candidate)

    def _clear_cart(self) -> None:
        self._commit_cart(Cart())

    def load_sale_lines(self, lines: list[dict[str, int]]) -> bool:
        """Replace the current cart with a recalled held sale."""
        candidate = Cart()
        try:
            for line in lines:
                candidate.add(int(line["item_id"]), int(line["quantity_milli"]))
        except (KeyError, TypeError, ValueError, PosError) as error:
            self.toast.show_message(getattr(error, "message", t("invalid_held_sale", "This held sale cannot be recalled.")))
            return False
        return self._commit_cart(candidate)

    def hold_current_sale(self) -> None:
        """Save this cart for later, without changing stock."""
        if not len(self.cart):
            return
        try:
            self.context.sales.hold_sale(self.cart.to_sale_lines())
        except PosError as error:
            self.toast.show_message(error.message)
            return
        self._clear_cart()
        self.toast.show_message(t("sale_held", "Sale saved for later."))

    def _render_cart(self) -> None:
        self._clear_layout(self.cart_lines_layout)
        selected_ids = {line.item_id for line in self.cart.lines()}
        for card in self._product_cards:
            selected = card.item_id in selected_ids
            card.set_selected(selected)
        has_lines = self.quote is not None
        if has_lines and self.quote is not None:
            for line in self.quote["lines"]:
                widget = CartLineItem(line, self.currency)
                widget.quantity_changed.connect(self._set_quantity)
                widget.remove_requested.connect(self._remove_item)
                self.cart_lines_layout.addWidget(widget)
            self.subtotal_label.setText(
                f"{t('subtotal', 'Subtotal')}: {fmt(int(self.quote['subtotal_minor']), self.currency)}"
            )
            self.tax_label.setText(
                f"{t('tax', 'Tax')}: {fmt(int(self.quote['tax_minor']), self.currency)}"
            )
            self.discount_label.setText(
                f"{t('discount', 'Discount')}: {fmt(int(self.quote['discount_minor']), self.currency)}"
            )
            self.total_label.setText(
                f"{t('total', 'Total')}: {fmt(int(self.quote['total_minor']), self.currency)}"
            )
        else:
            empty = QLabel(t("cart_empty", "Your sale is empty. Add items from the catalogue."))
            empty.setWordWrap(True)
            self.cart_lines_layout.addWidget(empty)
            zero = fmt(0, self.currency)
            self.subtotal_label.setText(f"{t('subtotal', 'Subtotal')}: {zero}")
            self.tax_label.setText(f"{t('tax', 'Tax')}: {zero}")
            self.discount_label.setText(f"{t('discount', 'Discount')}: {zero}")
            self.total_label.setText(f"{t('total', 'Total')}: {zero}")
        self.pay_button.setEnabled(has_lines)
        self.hold_button.setEnabled(has_lines)

    def _open_payment(self) -> None:
        if self.quote is None:
            return
        methods = [
            str(row["name"]) for row in self.context.settings.payment_methods()
            if row["active"]
        ]
        if not methods:
            self.toast.show_message(t("no_payment_methods", "Enable a payment method in Settings first."))
            return
        user = self.context.auth.current_user
        dialog = PaymentDialog(
            self.context.sales, self.cart.to_sale_lines(), self.quote, methods,
            currency=self.currency, user_id=user.id if user else None, parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_sale is not None:
            sale: SaleResult = dialog.result_sale
            self._commit_cart(Cart())
            self.sale_completed.emit(sale)

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

