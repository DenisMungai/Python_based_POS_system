"""Service-backed catalogue and inventory management view."""

from decimal import Decimal
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.errors import PosError, PermissionDeniedError
from backend.core.money import fmt, milli_to_qty, qty_to_milli, to_minor
from gui.dialogs.csv_import import CsvImportPreviewDialog
from gui.i18n import t
from gui.styles.tokens import px
from gui.widgets import (
    Toast, clear_table_widgets, configure_table, fit_table_action_column,
    set_table_action_cell,
)


class CategoryDialog(QDialog):
    """Create a catalogue category through CatalogService."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(t("add_category", "Add category"))
        self.setModal(True)
        self.setMinimumWidth(px(380))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(12))
        title = QLabel(t("add_category", "Add category"))
        title.setObjectName("drawerTitle")
        layout.addWidget(title)
        self.name = QLineEdit()
        self.name.setPlaceholderText(t("category_name", "Category name"))
        layout.addWidget(self.name)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        create = QPushButton(t("create", "Create"))
        create.setProperty("primary", True)
        create.clicked.connect(self._create)
        actions.addWidget(cancel)
        actions.addWidget(create)
        layout.addLayout(actions)
        self.name.returnPressed.connect(self._create)

    def _create(self) -> None:
        try:
            self.context.catalog.create_category(self.name.text())
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            return
        self.accept()


class ItemDialog(QDialog):
    """Create or edit a catalogue item."""

    def __init__(
        self, context: AppContext, item: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.item = item
        self.setWindowTitle(t("edit_item", "Edit item") if item else t("add_item", "Add item"))
        self.setModal(True)
        self.setMinimumWidth(px(520))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(12))
        title = QLabel(t("edit_item", "Edit item") if item else t("add_item", "Add item"))
        title.setObjectName("drawerTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.setSpacing(px(9))

        self.name = QLineEdit(str(item["name"]) if item else "")
        self.description = QLineEdit(str(item["description"]) if item and item["description"] else "")
        self.item_type = QComboBox()
        self.item_type.addItems(["product", "service", "weighed", "bundle", "non_inventory"])
        if item:
            self.item_type.setCurrentText(str(item["item_type"]))
        self.category = QComboBox()
        self.category.addItem(t("uncategorized", "Uncategorized"), None)
        for category in context.catalog.list_categories():
            self.category.addItem(str(category["name"]), int(category["id"]))
        if item and item["category_id"] is not None:
            index = self.category.findData(int(item["category_id"]))
            if index >= 0:
                self.category.setCurrentIndex(index)
        self.unit = QLineEdit(str(item["unit"]) if item else "each")
        self.barcode = QLineEdit(str(item["barcode"]) if item and item["barcode"] else "")
        self.price = QLineEdit(
            str(Decimal(int(item["price_minor"])).scaleb(-2)) if item else "0"
        )
        self.cost = QLineEdit(
            str(Decimal(int(item["cost_minor"])).scaleb(-2)) if item else "0"
        )
        self.low_stock = QLineEdit(
            str(milli_to_qty(int(item["low_stock_milli"]))) if item else "0"
        )
        self.opening_stock = QLineEdit("0")
        self.tax_inclusive = QCheckBox(t("tax_inclusive", "Tax inclusive"))
        self.image_source: Path | None = None
        image_row = QWidget()
        image_layout = QHBoxLayout(image_row)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(px(8))
        self.image_preview = QLabel()
        self.image_preview.setObjectName("productThumbnail")
        self.image_preview.setFixedSize(px(72), px(72))
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_status = QLabel(
            t("product_image_attached", "Image added")
            if item and item.get("image_path") else
            t("no_product_image", "No image selected")
        )
        self.image_status.setObjectName("mutedText")
        if item and item.get("image_path"):
            self._show_image_preview(Path(str(item["image_path"])))
        else:
            self.image_preview.setText(self.name.text()[:1].upper())
        choose_image = QPushButton(t("choose_image", "Choose image"))
        choose_image.clicked.connect(self._choose_image)
        image_layout.addWidget(self.image_preview)
        image_layout.addWidget(self.image_status, 1)
        image_layout.addWidget(choose_image)
        if item:
            self.tax_inclusive.setChecked(bool(item["tax_inclusive"]))

        form.addRow(t("name", "Name"), self.name)
        form.addRow(t("description", "Description"), self.description)
        form.addRow(t("item_type", "Item type"), self.item_type)
        form.addRow(t("category", "Category"), self.category)
        form.addRow(t("unit", "Unit"), self.unit)
        form.addRow(t("barcode", "Barcode"), self.barcode)
        form.addRow(t("price", "Price"), self.price)
        form.addRow(t("cost", "Cost"), self.cost)
        form.addRow(t("low_stock", "Low-stock threshold"), self.low_stock)
        form.addRow(t("product_image", "Product image"), image_row)
        if item is None:
            form.addRow(t("opening_stock", "Opening stock"), self.opening_stock)
        form.addRow("", self.tax_inclusive)
        layout.addLayout(form)

        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(t("save", "Save"))
        save.setProperty("primary", True)
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _save(self) -> None:
        try:
            price_minor = to_minor(self.price.text())
            cost_minor = to_minor(self.cost.text())
            low_stock_milli = qty_to_milli(self.low_stock.text())
            fields: dict[str, Any] = {
                "name": self.name.text(),
                "description": self.description.text(),
                "item_type": self.item_type.currentText(),
                "category_id": self.category.currentData(),
                "unit": self.unit.text(),
                "barcode": self.barcode.text().strip() or None,
                "price_minor": price_minor,
                "cost_minor": cost_minor,
                "low_stock_milli": low_stock_milli,
                "tax_inclusive": int(self.tax_inclusive.isChecked()),
            }
            if self.item is None:
                fields["stock_milli"] = qty_to_milli(self.opening_stock.text())
                item_id = self.context.catalog.create_item(
                    self.name.text(), price_minor,
                    description=self.description.text(), category_id=self.category.currentData(),
                    item_type=self.item_type.currentText(), unit=self.unit.text(),
                    barcode=self.barcode.text().strip() or None, cost_minor=cost_minor,
                    low_stock_milli=low_stock_milli,
                    stock_milli=fields["stock_milli"],
                    tax_inclusive=int(self.tax_inclusive.isChecked()),
                )
            else:
                self.context.catalog.update_item(int(self.item["id"]), **fields)
                item_id = int(self.item["id"])
            if self.image_source is not None:
                self.context.catalog.set_item_image(item_id, self.image_source)
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            return
        self.accept()

    def _choose_image(self) -> None:
        """Select a local product image for safe service-managed import."""
        selected, _ = QFileDialog.getOpenFileName(
            self, t("choose_image", "Choose image"), "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not selected:
            return
        self.image_source = Path(selected)
        self.image_status.setText(self.image_source.name)
        self._show_image_preview(self.image_source)

    def _show_image_preview(self, image_path: Path) -> None:
        image = QPixmap(str(image_path))
        if image.isNull():
            self.image_preview.setText(t("image_unavailable", "Unavailable"))
            return
        self.image_preview.setPixmap(image.scaled(
            self.image_preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))


class StockAdjustmentDialog(QDialog):
    """Apply a signed stock adjustment through InventoryService."""

    def __init__(
        self, context: AppContext, item: dict[str, Any], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.item = item
        self.setWindowTitle(t("adjust_stock", "Adjust stock"))
        self.setModal(True)
        self.setMinimumWidth(px(420))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(12))
        title = QLabel(f"{t('adjust_stock', 'Adjust stock')}: {item['name']}")
        title.setObjectName("drawerTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.setSpacing(px(9))
        self.quantity = QLineEdit("1")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText(t("adjustment_reason", "Adjustment reason"))
        form.addRow(t("quantity_change", "Quantity change"), self.quantity)
        form.addRow(t("reason", "Reason"), self.reason)
        layout.addLayout(form)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        apply = QPushButton(t("apply", "Apply"))
        apply.setProperty("primary", True)
        apply.clicked.connect(self._apply)
        actions.addWidget(cancel)
        actions.addWidget(apply)
        layout.addLayout(actions)

    def _apply(self) -> None:
        try:
            delta_milli = qty_to_milli(self.quantity.text())
            user = self.context.auth.current_user
            self.context.inventory.adjust_stock(
                int(self.item["id"]), delta_milli, self.reason.text(),
                user_id=user.id if user else None,
            )
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            return
        self.accept()


class ArchiveItemDialog(QDialog):
    """Confirm irreversible removal from the active catalogue."""

    def __init__(
        self, context: AppContext, item: dict[str, Any], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.item = item
        self.setWindowTitle(t("archive_item", "Archive item"))
        self.setModal(True)
        self.setMinimumWidth(px(420))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(12))
        message = QLabel(t("archive_confirmation", "Archive this item? It remains in historical sales."))
        message.setWordWrap(True)
        layout.addWidget(message)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        archive = QPushButton(t("archive", "Archive"))
        archive.setProperty("primary", True)
        archive.clicked.connect(self._archive)
        actions.addWidget(cancel)
        actions.addWidget(archive)
        layout.addLayout(actions)

    def _archive(self) -> None:
        try:
            self.context.catalog.archive_item(int(self.item["id"]))
        except PosError as error:
            Toast(self).show_message(error.message)
            return
        self.accept()


class ProductsView(QWidget):
    """Search, edit, classify, and adjust catalogue items."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.currency = context.settings.get("currency") or "KES"
        self.toast = Toast(self)
        self.category_id: int | None = None
        self.can_write = True
        self.can_adjust = True
        try:
            context.auth.require_permission("catalog.write")
        except PermissionDeniedError:
            self.can_write = False
        try:
            context.auth.require_permission("inventory.adjust")
        except PermissionDeniedError:
            self.can_adjust = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(14))
        heading = QLabel(t("products", "Products"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(px(8))
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("search_catalogue", "Search catalogue"))
        self.search.textChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(self.search, 1)
        self.category_filter = QComboBox()
        self.category_filter.currentIndexChanged.connect(self._category_changed)
        toolbar.addWidget(self.category_filter)
        self.add_category_button = QPushButton(t("add_category", "Add category"))
        self.add_category_button.clicked.connect(self._add_category)
        self.add_category_button.setEnabled(self.can_write)
        toolbar.addWidget(self.add_category_button)
        self.add_item_button = QPushButton(t("add_item", "Add item"))
        self.add_item_button.setProperty("primary", True)
        self.add_item_button.clicked.connect(lambda: self._edit_item(None))
        self.add_item_button.setEnabled(self.can_write)
        toolbar.addWidget(self.add_item_button)
        export = QPushButton(t("export_csv", "Export CSV"))
        export.clicked.connect(self._export_csv)
        toolbar.addWidget(export)
        self.import_button = QPushButton(t("import_csv", "Import CSV"))
        self.import_button.clicked.connect(self._import_csv)
        self.import_button.setEnabled(self.can_write)
        toolbar.addWidget(self.import_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        configure_table(self.table)
        self.table.setObjectName("catalogueTable")
        self.table.setHorizontalHeaderLabels([
            t("name", "Name"), t("item_type", "Type"), t("category", "Category"),
            t("barcode", "Barcode"), t("price", "Price"), t("stock", "Stock"),
            t("actions", "Actions"),
        ])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self._load_categories()
        self.refresh()

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _load_categories(self) -> None:
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem(t("all_items", "All items"), None)
        for category in self.context.catalog.list_categories():
            self.category_filter.addItem(str(category["name"]), int(category["id"]))
        self.category_filter.blockSignals(False)

    def _category_changed(self, index: int) -> None:
        self.category_id = self.category_filter.itemData(index)
        self.refresh()

    def _add_category(self) -> None:
        dialog = CategoryDialog(self.context, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_categories()
            self.refresh()

    def _edit_item(self, item: dict[str, Any] | None) -> None:
        if not self.can_write:
            return
        dialog = ItemDialog(self.context, item, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _adjust_stock(self, item: dict[str, Any]) -> None:
        if not self.can_adjust:
            return
        dialog = StockAdjustmentDialog(self.context, item, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _archive_item(self, item: dict[str, Any]) -> None:
        if not self.can_write:
            return
        dialog = ArchiveItemDialog(self.context, item, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _export_csv(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, t("export_items", "Export items"), "items.csv",
            "CSV files (*.csv)",
        )
        if not selected:
            return
        try:
            path = self.context.imports.export_items_csv(Path(selected))
            self.toast.show_message(t("export_complete", "CSV exported.") + f" {path.name}")
        except PosError as error:
            self.toast.show_message(error.message)

    def _import_csv(self) -> None:
        if not self.can_write:
            return
        selected, _ = QFileDialog.getOpenFileName(
            self, t("import_items", "Import items"), "", "CSV files (*.csv)",
        )
        if not selected:
            return
        try:
            content = Path(selected).read_text(encoding="utf-8-sig")
            preview = self.context.imports.preview_items_csv(content)
        except PosError as error:
            self.toast.show_message(error.message)
            return
        except (OSError, UnicodeError):
            self.toast.show_message(t("csv_read_failed", "Could not read the selected CSV file."))
            return
        dialog = CsvImportPreviewDialog(t("import_items", "Import items"), preview, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.context.imports.import_items_csv(content, dry_run=False)
            self.toast.show_message(t("import_complete", "Items imported."))
            self.refresh()
        except PosError as error:
            self.toast.show_message(error.message)

    def refresh(self) -> None:
        try:
            items = self.context.catalog.search_items(
                self.search.text().strip(), category_id=self.category_id, limit=500,
            )
        except PosError as error:
            self.toast.show_message(error.message)
            return
        categories = {int(row["id"]): str(row["name"]) for row in self.context.catalog.list_categories()}
        clear_table_widgets(self.table)
        self.table.setRowCount(len(items))
        for row_index, item in enumerate(items):
            category = categories.get(int(item["category_id"])) if item["category_id"] is not None else ""
            stock_milli = int(item["stock_milli"])
            item_type = str(item["item_type"])
            stock = (
                t("available", "Available")
                if item_type in {"service", "non_inventory"}
                else f"{milli_to_qty(stock_milli):g}"
            )
            values = (
                str(item["name"]), item_type, category or t("uncategorized", "Uncategorized"),
                str(item["barcode"] or ""), fmt(int(item["price_minor"]), self.currency),
                stock,
            )
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(px(4), px(4), px(4), px(4))
            actions_layout.setSpacing(px(6))
            edit = QPushButton(t("edit", "Edit"))
            edit.setEnabled(self.can_write)
            edit.clicked.connect(lambda _, row=item: self._edit_item(row))
            actions_layout.addWidget(edit)
            if item_type in {"product", "weighed", "bundle"}:
                adjust = QPushButton(t("adjust", "Adjust"))
                adjust.setEnabled(self.can_adjust)
                adjust.clicked.connect(lambda _, row=item: self._adjust_stock(row))
                actions_layout.addWidget(adjust)
            archive = QPushButton(t("archive", "Archive"))
            archive.setEnabled(self.can_write)
            archive.clicked.connect(lambda _, row=item: self._archive_item(row))
            actions_layout.addWidget(archive)
            set_table_action_cell(self.table, row_index, 6, actions)
            self.table.setRowHeight(row_index, px(68))
        self.table.resizeColumnsToContents()
        fit_table_action_column(self.table, 6)
