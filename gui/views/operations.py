"""Customer, sales, return, and discount management views."""

from datetime import datetime
from typing import Any
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.errors import PermissionDeniedError, PosError
from backend.core.money import fmt, qty_to_milli, to_minor
from gui.dialogs.csv_import import CsvImportPreviewDialog
from gui.i18n import t
from gui.styles.tokens import px
from gui.widgets import (
    ReceiptWidget, Toast, clear_table_widgets, configure_table,
    fit_table_action_column, set_table_action_cell,
)


class CustomerDialog(QDialog):
    def __init__(self, context: AppContext, customer: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context, self.customer = context, customer
        self.setWindowTitle(t("edit_customer", "Edit customer") if customer else t("add_customer", "Add customer"))
        self.setModal(True)
        self.setMinimumWidth(px(460))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(10))
        form = QFormLayout()
        self.name = QLineEdit(str(customer["name"]) if customer else "")
        self.phone = QLineEdit(str(customer["phone"]) if customer else "")
        self.email = QLineEdit(str(customer["email"]) if customer else "")
        self.notes = QTextEdit(str(customer["notes"]) if customer else "")
        self.notes.setMaximumHeight(px(100))
        form.addRow(t("name", "Name"), self.name)
        form.addRow(t("phone", "Phone"), self.phone)
        form.addRow(t("email", "Email"), self.email)
        form.addRow(t("notes", "Notes"), self.notes)
        layout.addLayout(form)
        self.error = QLabel()
        self.error.setObjectName("errorMessage")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
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
        fields = {
            "name": self.name.text(), "phone": self.phone.text(),
            "email": self.email.text(), "notes": self.notes.toPlainText(),
        }
        try:
            if self.customer:
                self.context.customers.update(int(self.customer["id"]), **fields)
            else:
                self.context.customers.register(
                    self.name.text(), self.phone.text(), self.email.text(), self.notes.toPlainText()
                )
        except PosError as error:
            self.error.setText(error.message)
            self.error.show()
            return
        self.accept()


class CustomerHistoryDialog(QDialog):
    def __init__(
        self, context: AppContext, customer_id: int, currency: str,
        can_write: bool, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context, self.customer_id = context, customer_id
        self.currency, self.can_write = currency, can_write
        self.setWindowTitle(t("customer_history", "Customer history"))
        self.setModal(True)
        self.resize(px(720), px(520))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(10))
        self.heading = QLabel()
        self.heading.setObjectName("drawerTitle")
        layout.addWidget(self.heading)
        self.credit_label = QLabel()
        layout.addWidget(self.credit_label)

        if can_write:
            credit_row = QHBoxLayout()
            self.credit_amount = QLineEdit()
            self.credit_amount.setPlaceholderText(t("credit_amount", "Credit amount"))
            credit_row.addWidget(self.credit_amount, 1)
            add_credit = QPushButton(t("add_credit", "Add store credit"))
            add_credit.clicked.connect(self._add_credit)
            credit_row.addWidget(add_credit)
            layout.addLayout(credit_row)

        self.error = QLabel()
        self.error.setObjectName("errorMessage")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        self.table = QTableWidget(0, 4)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("receipt", "Receipt"), t("date", "Date"), t("status", "Status"),
            t("total", "Total"),
        ])
        layout.addWidget(self.table, 1)
        done = QPushButton(t("done", "Done"))
        done.setProperty("primary", True)
        done.clicked.connect(self.accept)
        layout.addWidget(done)
        self._refresh()

    def _refresh(self) -> None:
        record = self.context.customers.get_with_history(self.customer_id)
        customer = record["customer"]
        self.heading.setText(str(customer["name"]))
        self.credit_label.setText(
            f"{t('store_credit', 'Store credit')}: "
            f"{fmt(int(customer['credit_minor']), self.currency)}"
        )
        sales = record["sales"]
        self.table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            values = (
                str(sale["receipt_number"]), str(sale["created_at"]),
                str(sale["status"]), fmt(int(sale["total_minor"]), self.currency),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

    def _add_credit(self) -> None:
        try:
            amount_minor = to_minor(self.credit_amount.text())
            self.context.customers.add_store_credit(self.customer_id, amount_minor)
            self.credit_amount.clear()
            self.error.hide()
            self._refresh()
        except PosError as error:
            self.error.setText(error.message)
            self.error.show()


class CustomersView(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context, self.toast = context, Toast(self)
        self.currency = context.settings.get("currency") or "KES"
        self.can_write = True
        try:
            context.auth.require_permission("customers.write")
        except PermissionDeniedError:
            self.can_write = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(14))
        heading = QLabel(t("customers", "Customers"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("search_customers", "Search customers"))
        self.search.textChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(self.search, 1)
        export = QPushButton(t("export_csv", "Export CSV"))
        export.clicked.connect(self._export_csv)
        toolbar.addWidget(export)
        self.import_button = QPushButton(t("import_csv", "Import CSV"))
        self.import_button.clicked.connect(self._import_csv)
        self.import_button.setEnabled(self.can_write)
        toolbar.addWidget(self.import_button)
        add = QPushButton(t("add_customer", "Add customer"))
        add.setProperty("primary", True)
        add.clicked.connect(lambda: self._edit(None))
        add.setEnabled(self.can_write)
        toolbar.addWidget(add)
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, 5)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("name", "Name"), t("phone", "Phone"), t("email", "Email"),
            t("store_credit", "Store credit"), t("actions", "Actions"),
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.refresh()

    def _edit(self, customer: dict[str, Any] | None) -> None:
        if not self.can_write:
            return
        dialog = CustomerDialog(self.context, customer, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _show_history(self, customer: dict[str, Any]) -> None:
        try:
            dialog = CustomerHistoryDialog(
                self.context, int(customer["id"]), self.currency, self.can_write, self,
            )
            dialog.exec()
            self.refresh()
        except PosError as error:
            self.toast.show_message(error.message)

    def _export_csv(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, t("export_customers", "Export customers"), "customers.csv",
            "CSV files (*.csv)",
        )
        if not selected:
            return
        try:
            path = self.context.imports.export_customers_csv(Path(selected))
            self.toast.show_message(t("export_complete", "CSV exported.") + f" {path.name}")
        except PosError as error:
            self.toast.show_message(error.message)

    def _import_csv(self) -> None:
        if not self.can_write:
            return
        selected, _ = QFileDialog.getOpenFileName(
            self, t("import_customers", "Import customers"), "", "CSV files (*.csv)",
        )
        if not selected:
            return
        try:
            content = Path(selected).read_text(encoding="utf-8-sig")
            preview = self.context.imports.preview_customers_csv(content)
        except PosError as error:
            self.toast.show_message(error.message)
            return
        except (OSError, UnicodeError):
            self.toast.show_message(t("csv_read_failed", "Could not read the selected CSV file."))
            return
        dialog = CsvImportPreviewDialog(t("import_customers", "Import customers"), preview, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.context.imports.import_customers_csv(content, dry_run=False)
            self.toast.show_message(t("import_complete", "Customers imported."))
            self.refresh()
        except PosError as error:
            self.toast.show_message(error.message)

    def refresh(self) -> None:
        try:
            customers = self.context.customers.search(self.search.text().strip(), limit=500)
        except PosError as error:
            self.toast.show_message(error.message)
            return
        clear_table_widgets(self.table)
        self.table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            values = (
                str(customer["name"]), str(customer["phone"]), str(customer["email"]),
                fmt(int(customer["credit_minor"]), self.currency),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            history = QPushButton(t("history", "History"))
            history.clicked.connect(lambda _, item=customer: self._show_history(item))
            action_layout.addWidget(history)
            edit = QPushButton(t("edit", "Edit"))
            edit.setEnabled(self.can_write)
            edit.clicked.connect(lambda _, item=customer: self._edit(item))
            action_layout.addWidget(edit)
            self.table.setCellWidget(row, 4, actions)
            self.table.setRowHeight(row, px(64))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)


class SalesView(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context, self.currency = context, context.settings.get("currency") or "KES"
        self.toast = Toast(self)
        self.can_void = True
        try:
            context.auth.require_permission("sales.void")
        except PermissionDeniedError:
            self.can_void = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(12))
        heading = QLabel(t("sales_history", "Sales history"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        self.table = QTableWidget(0, 7)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("receipt", "Receipt"), t("date", "Date"), t("status", "Status"),
            t("subtotal", "Subtotal"), t("discount", "Discount"), t("total", "Total"),
            t("actions", "Actions"),
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        try:
            sales = self.context.sales.list_sales(limit=500)
        except PosError as error:
            self.toast.show_message(error.message)
            return
        self._sales = sales
        clear_table_widgets(self.table)
        self.table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            created_at = datetime.fromisoformat(str(sale["created_at"])).astimezone()
            values = (
                str(sale["receipt_number"]), created_at.strftime("%Y-%m-%d %H:%M"),
                str(sale["status"]),
                fmt(int(sale["subtotal_minor"]), self.currency),
                fmt(int(sale["discount_minor"]), self.currency),
                fmt(int(sale["total_minor"]), self.currency),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(px(4), px(3), px(4), px(3))
            view = QPushButton(t("view_receipt", "Receipt"))
            view.clicked.connect(lambda _, item=sale: self._view_receipt(item))
            action_layout.addWidget(view)
            if self.can_void and sale["status"] == "completed":
                void = QPushButton(t("void_sale", "Void"))
                void.clicked.connect(lambda _, item=sale: self._void_sale(item))
                action_layout.addWidget(void)
            set_table_action_cell(self.table, row, 6, actions)
            self.table.setRowHeight(row, px(68))
        self.table.resizeColumnsToContents()
        fit_table_action_column(self.table, 6)

    def _view_receipt(self, sale: dict[str, Any]) -> None:
        dialog = QDialog(self)
        dialog.setModal(True)
        dialog.setWindowTitle(str(sale["receipt_number"]))
        dialog.resize(px(500), px(620))
        dialog_layout = QVBoxLayout(dialog)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        scroll.setWidget(ReceiptWidget(self.context.receipts, int(sale["id"])))
        dialog_layout.addWidget(scroll, 1)
        done = QPushButton(t("done", "Done"))
        done.setProperty("primary", True)
        done.clicked.connect(dialog.accept)
        dialog_layout.addWidget(done)
        dialog.exec()

    def _void_sale(self, sale: dict[str, Any]) -> None:
        if not self.can_void:
            return
        dialog = VoidSaleDialog(self.context, sale, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()


class VoidSaleDialog(QDialog):
    def __init__(
        self, context: AppContext, sale: dict[str, Any], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context, self.sale = context, sale
        self.setWindowTitle(t("void_sale", "Void sale"))
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(10))
        message = QLabel(
            t("void_confirmation", "Void sale {receipt}? This action is recorded in the audit log.").format(
                receipt=sale["receipt_number"],
            )
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        self.reason = QLineEdit()
        self.reason.setPlaceholderText(t("void_reason", "Reason for voiding"))
        layout.addWidget(self.reason)
        self.error = QLabel()
        self.error.setObjectName("errorMessage")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        confirm = QPushButton(t("void_sale", "Void sale"))
        confirm.setProperty("primary", True)
        confirm.clicked.connect(self._submit)
        actions.addWidget(cancel)
        actions.addWidget(confirm)
        layout.addLayout(actions)

    def _submit(self) -> None:
        user = self.context.auth.current_user
        try:
            self.context.sales.void_sale(
                int(self.sale["id"]), self.reason.text(),
                user_id=user.id if user else None,
            )
        except PosError as error:
            self.error.setText(error.message)
            self.error.show()
            return
        self.accept()


class OrdersView(QWidget):
    """Review held orders and recall one into the active checkout."""

    recall_requested = Signal(object)

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.toast = Toast(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(12))
        heading = QLabel(t("orders", "Orders"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        self.table = QTableWidget(0, 4)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("created", "Saved"), t("items", "Items"), t("note", "Note"),
            t("actions", "Actions"),
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        try:
            held = self.context.sales.list_held(limit=500)
        except PosError as error:
            self.toast.show_message(error.message)
            return
        clear_table_widgets(self.table)
        self.table.setRowCount(len(held))
        for row, sale in enumerate(held):
            created = str(sale["created_at"]).replace("T", " ")[:16]
            self.table.setItem(row, 0, QTableWidgetItem(created))
            self.table.setItem(row, 1, QTableWidgetItem(str(len(sale["lines"]))))
            self.table.setItem(row, 2, QTableWidgetItem(str(sale.get("note") or "")))
            recall = QPushButton(t("recall", "Recall"))
            recall.clicked.connect(lambda _, item=sale: self._recall(item))
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(px(4), px(3), px(4), px(3))
            actions_layout.addWidget(recall)
            actions_layout.addStretch(1)
            self.table.setCellWidget(row, 3, actions)
            self.table.setRowHeight(row, px(64))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _recall(self, sale: dict[str, Any]) -> None:
        try:
            recalled = self.context.sales.recall_held(int(sale["id"]), remove=False)
        except PosError as error:
            self.toast.show_message(error.message)
            self.refresh()
            return
        self.recall_requested.emit(recalled)


class ReturnDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(t("process_return", "Process return"))
        self.setModal(True)
        self.setMinimumWidth(px(620))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(10))
        lookup = QHBoxLayout()
        self.receipt = QLineEdit()
        self.receipt.setPlaceholderText(t("receipt_number", "Receipt number"))
        lookup.addWidget(self.receipt, 1)
        find = QPushButton(t("find", "Find"))
        find.clicked.connect(self._find)
        lookup.addWidget(find)
        layout.addLayout(lookup)
        self.table = QTableWidget(0, 4)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("item", "Item"), t("sold", "Sold"), t("return_quantity", "Return quantity"),
            t("restock", "Restock"),
        ])
        layout.addWidget(self.table, 1)
        self.note = QLineEdit()
        self.note.setPlaceholderText(t("return_note", "Return note"))
        layout.addWidget(self.note)
        self.error = QLabel()
        self.error.setObjectName("errorMessage")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        submit = QPushButton(t("process_return", "Process return"))
        submit.setProperty("primary", True)
        submit.clicked.connect(self._submit)
        actions.addWidget(cancel)
        actions.addWidget(submit)
        layout.addLayout(actions)
        self.sale = None

    def _find(self) -> None:
        try:
            self.sale = self.context.returns.find_sale_by_receipt(self.receipt.text().strip())
        except PosError as error:
            self.error.setText(error.message)
            self.error.show()
            return
        self.error.hide()
        items = self.sale["items"]
        clear_table_widgets(self.table)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            remaining = int(item["quantity_milli"]) - int(item["returned_milli"])
            self.table.setItem(row, 0, QTableWidgetItem(str(item["name_snapshot"])))
            self.table.setItem(row, 1, QTableWidgetItem(str(remaining)))
            quantity = QLineEdit("0")
            quantity.setProperty("sale_item_id", int(item["id"]))
            quantity.setProperty("remaining_milli", remaining)
            self.table.setCellWidget(row, 2, quantity)
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.table.setCellWidget(row, 3, checkbox)

    def _submit(self) -> None:
        if self.sale is None:
            self.error.setText(t("find_receipt_first", "Find a receipt before processing a return."))
            self.error.show()
            return
        requests = []
        for row in range(self.table.rowCount()):
            quantity = self.table.cellWidget(row, 2)
            if quantity is None:
                continue
            text = quantity.text().strip()
            try:
                milli = qty_to_milli(text)
            except PosError:
                milli = -1
            if milli > 0:
                restock = self.table.cellWidget(row, 3)
                requests.append({
                    "sale_item_id": quantity.property("sale_item_id"),
                    "quantity_milli": milli,
                    "restock": bool(restock.isChecked()) if isinstance(restock, QCheckBox) else False,
                })
        try:
            user = self.context.auth.current_user
            self.context.returns.create_return(
                int(self.sale["id"]), requests,
                note=self.note.text(), user_id=user.id if user else None,
            )
        except PosError as error:
            self.error.setText(error.message)
            self.error.show()
            return
        self.accept()


class ReturnsView(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(12))
        heading = QLabel(t("returns", "Returns"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        button = QPushButton(t("process_return", "Process return"))
        button.setProperty("primary", True)
        button.clicked.connect(self._process_return)
        toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, 5)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("return_number", "Return"), t("receipt", "Receipt"), t("date", "Date"),
            t("total", "Total"), t("note", "Note"),
        ])
        layout.addWidget(self.table, 1)
        self.refresh()

    def _process_return(self) -> None:
        if ReturnDialog(self.context, self).exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def refresh(self) -> None:
        try:
            returns = self.context.returns.list_returns(limit=500)
        except PosError as error:
            Toast(self).show_message(error.message)
            return
        self.table.setRowCount(len(returns))
        currency = self.context.settings.get("currency") or "KES"
        for row, record in enumerate(returns):
            values = (
                str(record["return_number"]), str(record["receipt_number"]),
                str(record["created_at"]), fmt(int(record["total_minor"]), currency),
                str(record.get("note") or ""),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))



class VoucherDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(t("add_voucher", "Add voucher"))
        self.setModal(True)
        self.setMinimumWidth(px(460))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        form = QFormLayout()
        self.code = QLineEdit()
        self.kind = QLineEdit("fixed")
        self.value = QLineEdit("100")
        self.minimum = QLineEdit("0")
        form.addRow(t("code", "Code"), self.code)
        form.addRow(t("kind_percent_fixed", "Kind (percent/fixed)"), self.kind)
        form.addRow(t("value", "Value"), self.value)
        form.addRow(t("minimum_spend", "Minimum spend"), self.minimum)
        layout.addLayout(form)
        self.error = QLabel()
        self.error.setObjectName("errorMessage")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
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
            kind = self.kind.text().strip().lower()
            if kind == "fixed":
                value = int(float(self.value.text()) * 100)
            elif kind == "percent":
                value = int(float(self.value.text()) * 100)
            else:
                raise PosError("Voucher kind must be percent or fixed.")
            minimum = int(float(self.minimum.text()) * 100)
            self.context.discounts.create_voucher(
                self.code.text(), kind, value, minimum_minor=minimum
            )
        except PosError as error:
            self.error.setText(error.message)
            self.error.show()
            return
        except ValueError:
            self.error.setText(t("invalid_voucher_values", "Enter valid voucher values."))
            self.error.show()
            return
        self.accept()


class DiscountsView(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(12))
        heading = QLabel(t("discounts", "Discounts"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        add = QPushButton(t("add_voucher", "Add voucher"))
        add.setProperty("primary", True)
        add.clicked.connect(lambda: VoucherDialog(context, self).exec() and self.refresh())
        toolbar.addWidget(add)
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, 7)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("code", "Code"), t("kind", "Kind"), t("value", "Value"),
            t("minimum_spend", "Minimum"), t("used", "Used"), t("active", "Active"),
            t("actions", "Actions"),
        ])
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        try:
            vouchers = self.context.discounts.list_vouchers()
        except PosError as error:
            Toast(self).show_message(error.message)
            return
        clear_table_widgets(self.table)
        self.table.setRowCount(len(vouchers))
        for row, voucher in enumerate(vouchers):
            values = (
                str(voucher["code"]), str(voucher["kind"]), str(voucher["value"]),
                str(voucher["minimum_minor"]), str(voucher["used_count"]),
                t("yes", "Yes") if voucher["active"] else t("no", "No"),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            if voucher["active"]:
                deactivate = QPushButton(t("deactivate", "Deactivate"))
                deactivate.clicked.connect(lambda _, item=voucher: self._deactivate(item))
                self.table.setCellWidget(row, 6, deactivate)

    def _deactivate(self, voucher: dict[str, Any]) -> None:
        confirm = QDialog(self)
        confirm.setWindowTitle(t("deactivate_voucher", "Deactivate voucher"))
        confirm.setModal(True)
        layout = QVBoxLayout(confirm)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        message = QLabel(
            t("deactivate_voucher_confirmation", "Deactivate voucher {code}?").format(
                code=voucher["code"],
            )
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(confirm.reject)
        proceed = QPushButton(t("deactivate", "Deactivate"))
        proceed.setProperty("primary", True)
        proceed.clicked.connect(confirm.accept)
        actions.addWidget(cancel)
        actions.addWidget(proceed)
        layout.addLayout(actions)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.context.discounts.deactivate(int(voucher["id"]))
            self.refresh()
        except PosError as error:
            Toast(self).show_message(error.message)
