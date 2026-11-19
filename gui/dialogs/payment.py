"""Service-backed checkout dialog with configurable payment methods."""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from backend.core.errors import PosError
from backend.core.money import fmt, from_minor, to_minor
from backend.models.records import SaleResult
from backend.services.sales import SalesService
from gui.styles.tokens import px
from gui.i18n import t


class PaymentDialog(QDialog):
    """Collect payment details and commit a sale through SalesService."""

    def __init__(
        self,
        sales_service: SalesService,
        lines: list[dict[str, Any]],
        quote: dict[str, Any],
        payment_methods: list[str],
        currency: str,
        customer_id: int | None = None,
        voucher_code: str | None = None,
        user_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not payment_methods:
            raise ValueError("At least one payment method must be enabled.")
        self.sales_service = sales_service
        self.lines = lines
        self.quote = quote
        self.currency = currency
        self.customer_id = customer_id
        self.voucher_code = voucher_code
        self.user_id = user_id
        self.result_sale: SaleResult | None = None
        self.setWindowTitle(t("complete_sale", "Complete sale"))
        self.setModal(True)
        self.setMinimumWidth(px(420))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(14))
        title = QLabel(t("payment_method", "Payment method"))
        title.setObjectName("drawerTitle")
        layout.addWidget(title)
        total_line = QHBoxLayout()
        total_line.addWidget(QLabel(t("order_total", "Order total")), 1)
        self.total_label = QLabel(fmt(int(quote["total_minor"]), currency))
        self.total_label.setObjectName("receiptTotal")
        total_line.addWidget(self.total_label)
        layout.addLayout(total_line)

        self.method = QComboBox()
        self.method.addItems(payment_methods)
        self.method.currentTextChanged.connect(self._update_reference_visibility)
        self.amount = QLineEdit(f"{from_minor(int(quote['total_minor'])):f}")
        self.amount.setPlaceholderText(t("amount", "Amount received"))
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.reference = QLineEdit()
        self.reference.setPlaceholderText(
            t("confirmed_mpesa_reference", "Confirmed M-Pesa reference")
        )
        layout.addWidget(self.method)
        layout.addWidget(self.amount)
        layout.addWidget(self.reference)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        complete = QPushButton(t("complete_sale", "Complete sale"))
        complete.setProperty("checkout", True)
        complete.clicked.connect(self._complete)
        actions.addWidget(cancel)
        actions.addWidget(complete)
        layout.addLayout(actions)
        self._update_reference_visibility(self.method.currentText())
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._complete)

    def _update_reference_visibility(self, method: str) -> None:
        """Show the reference field only for M-Pesa payments."""
        self.reference.setVisible(method.casefold() in {"m-pesa", "mpesa"})

    def _complete(self) -> None:
        """Validate entered tender and delegate all sale rules to the service."""
        try:
            amount_minor = to_minor(self.amount.text())
            payment = {
                "method": self.method.currentText(),
                "amount_minor": amount_minor,
                "reference": self.reference.text().strip(),
            }
            self.result_sale = self.sales_service.process_sale(
                self.lines, [payment], customer_id=self.customer_id,
                voucher_code=self.voucher_code, user_id=self.user_id,
            )
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            return
        self.accept()
