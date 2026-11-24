"""Successful checkout, animated saved receipt, and local printing."""

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QSizeF, QTimer, Qt,
)
from PySide6.QtGui import QFont, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout,
)

from backend.bootstrap import AppContext
from backend.core.money import fmt
from backend.core.errors import PosError
from backend.models.records import SaleResult
from gui.i18n import t
from gui.styles.fonts import fpx, receipt_font_family
from gui.styles.tokens import px
from gui.widgets import ReceiptWidget


class SaleCompleteDialog(QDialog):
    """Show payment success, animate the saved receipt, and offer local printing."""

    def __init__(self, context: AppContext, sale: SaleResult) -> None:
        super().__init__()
        self.context = context
        self.sale = sale
        self.setWindowTitle(t("sale_complete", "Sale complete"))
        self.setModal(True)
        self.setMinimumWidth(px(500))
        self.setMinimumHeight(px(620))
        self.resize(px(540), px(620))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(20), px(24), px(20))
        layout.setSpacing(px(12))
        heading = QLabel(t("payment_success", "Payment received"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)

        self.status_label = QLabel(t("generating_receipt", "Generating your receipt…"))
        self.status_label.setObjectName("mutedText")
        layout.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setObjectName("receiptProgress")
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        number = QLabel(sale.receipt_number)
        number.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(number)
        if sale.change_minor:
            currency = context.settings.get("currency")
            if not currency:
                raise RuntimeError("The business currency is not configured.")
            change = QLabel(f"{t('change_due', 'Change due')}: {fmt(sale.change_minor, currency)}")
            change.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(change)

        self.receipt = ReceiptWidget(context.receipts, sale.id)
        self.receipt_scroll = QScrollArea()
        self.receipt_scroll.setWidgetResizable(True)
        self.receipt_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.receipt_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.receipt_scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.receipt_scroll.setWidget(self.receipt)
        self.receipt_scroll.setMinimumHeight(0)
        self.receipt_scroll.setMaximumHeight(0)
        layout.addWidget(self.receipt_scroll)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.save_text_button = QPushButton(t("save_text", "Save text"))
        self.save_text_button.setEnabled(False)
        self.save_text_button.clicked.connect(self._save_text)
        actions.addWidget(self.save_text_button)
        self.save_pdf_button = QPushButton(t("save_pdf", "Save PDF"))
        self.save_pdf_button.setEnabled(False)
        self.save_pdf_button.clicked.connect(self._save_pdf)
        actions.addWidget(self.save_pdf_button)
        self.print_button = QPushButton(t("print_receipt", "Print receipt"))
        self.print_button.setEnabled(False)
        self.print_button.clicked.connect(self._print_receipt)
        actions.addWidget(self.print_button)
        self.done_button = QPushButton(t("done", "Done"))
        self.done_button.setProperty("primary", True)
        self.done_button.setEnabled(False)
        self.done_button.clicked.connect(self.accept)
        actions.addWidget(self.done_button)
        layout.addLayout(actions)

        self._animations = QParallelAnimationGroup(self)
        self._reveal_animation = QPropertyAnimation(
            self.receipt_scroll, b"maximumHeight", self,
        )
        self._reveal_animation.setDuration(1050)
        self._reveal_animation.setStartValue(0)
        self._reveal_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animations.addAnimation(self._reveal_animation)
        progress_animation = QPropertyAnimation(self.progress, b"value", self)
        progress_animation.setDuration(1050)
        progress_animation.setStartValue(0)
        progress_animation.setEndValue(100)
        progress_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animations.addAnimation(progress_animation)
        self._animations.finished.connect(self._receipt_ready)
        QTimer.singleShot(0, self._start_receipt_animation)

    def _start_receipt_animation(self) -> None:
        """Measure the laid-out paper before starting its reveal animation."""
        self.receipt.adjustSize()
        height = min(max(self.receipt.sizeHint().height(), px(210)), px(390))
        self._reveal_animation.setEndValue(height)
        self._animations.start()

    def _receipt_ready(self) -> None:
        """Enable receipt actions once the saved receipt has been revealed."""
        self.status_label.setText(t("receipt_ready", "Receipt ready"))
        self.progress.hide()
        self.save_text_button.setEnabled(True)
        self.save_pdf_button.setEnabled(True)
        self.print_button.setEnabled(True)
        self.done_button.setEnabled(True)

    def _save_text(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, t("save_text_receipt", "Save text receipt"),
            f"{self.sale.receipt_number}.txt", "Text files (*.txt)",
        )
        if not selected:
            return
        try:
            path = self.context.receipts.export_text(self.sale.id, Path(selected))
            self.status_label.setText(
                t("receipt_saved", "Receipt saved.") + f" {path.name}"
            )
        except PosError as error:
            self.status_label.setText(error.message)
        except OSError:
            self.status_label.setText(
                t("receipt_save_failed", "Could not save the receipt. Check the selected location.")
            )
        self.status_label.show()

    def _save_pdf(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, t("save_pdf_receipt", "Save PDF receipt"),
            f"{self.sale.receipt_number}.pdf", "PDF files (*.pdf)",
        )
        if not selected:
            return
        target = Path(selected)
        try:
            self._write_pdf(target)
            self.status_label.setText(
                t("receipt_saved", "Receipt saved.") + f" {target.name}"
            )
        except PosError as error:
            self.status_label.setText(error.message)
        except (OSError, RuntimeError):
            self.status_label.setText(
                t("receipt_save_failed", "Could not save the receipt. Check the selected location.")
            )
        self.status_label.show()

    def _write_pdf(self, target: Path) -> None:
        temporary_path: str | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_path = tempfile.mkstemp(
                prefix=f".{target.stem}.", suffix=".pdf", dir=target.parent,
            )
            os.close(descriptor)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(temporary_path)
            receipt_text = self.context.receipts.render_text(self.sale.id)
            receipt_height_mm = max(60, len(receipt_text.splitlines()) * 4 + 16)
            printer.setPageSize(QPageSize(
                QSizeF(80, receipt_height_mm),
                QPageSize.Unit.Millimeter,
                "80 mm receipt",
            ))
            document = QTextDocument(self)
            font = QFont(receipt_font_family())
            font.setPixelSize(fpx("receipt"))
            document.setDefaultFont(font)
            document.setPlainText(receipt_text)
            document.print_(printer)
            del document, printer
            if not Path(temporary_path).is_file() or Path(temporary_path).stat().st_size == 0:
                raise OSError("PDF output is empty.")
            os.replace(temporary_path, target)
            temporary_path = None
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def _print_receipt(self) -> None:
        """Print the persisted thermal receipt through the local OS printer."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        try:
            receipt_text = self.context.receipts.render_text(self.sale.id)
            receipt_height_mm = max(60, len(receipt_text.splitlines()) * 4 + 16)
            printer.setPageSize(QPageSize(
                QSizeF(80, receipt_height_mm),
                QPageSize.Unit.Millimeter,
                "80 mm receipt",
            ))
            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle(t("print_receipt", "Print receipt"))
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            document = QTextDocument(self)
            font = QFont(receipt_font_family())
            font.setPixelSize(fpx("receipt"))
            document.setDefaultFont(font)
            document.setPlainText(receipt_text)
            document.print_(printer)
        except PosError as error:
            self.status_label.setText(error.message)
            self.status_label.show()
        except (OSError, RuntimeError):
            self.status_label.setText(
                t("print_failed", "Could not print the receipt. Check the selected printer and try again.")
            )
            self.status_label.show()
