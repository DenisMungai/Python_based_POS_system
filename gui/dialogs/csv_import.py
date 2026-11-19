"""Preview validated CSV rows before applying an import."""

from typing import Any

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from gui.i18n import t
from gui.styles.tokens import px
from gui.widgets import configure_table


class CsvImportPreviewDialog(QDialog):
    def __init__(
        self, title: str, preview: dict[str, Any], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(px(760), px(520))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        layout.setSpacing(px(10))

        rows = preview["rows"]
        errors = preview["errors"]
        summary = QLabel(
            t("csv_import_summary", "{rows} valid rows; {errors} errors").format(
                rows=len(rows), errors=len(errors),
            )
        )
        layout.addWidget(summary)
        self.table = QTableWidget(len(rows) + len(errors), 3)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("csv_row", "CSV row"), t("status", "Status"), t("details", "Details"),
        ])
        for index, row in enumerate(rows):
            self._set_row(index, int(row.get("__row__", index + 2)), "Ready", self._describe(row))
        offset = len(rows)
        for index, error in enumerate(errors):
            self._set_row(
                offset + index, int(error.get("row", 0)),
                t("error", "Error"), str(error.get("message", "")),
            )
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        self.import_button = QPushButton(t("import", "Import"))
        self.import_button.setProperty("primary", True)
        self.import_button.setEnabled(bool(rows) and not errors)
        self.import_button.clicked.connect(self.accept)
        actions.addWidget(self.import_button)
        layout.addLayout(actions)

    def _set_row(self, row: int, number: int, status: str, detail: str) -> None:
        self.table.setItem(row, 0, QTableWidgetItem(str(number)))
        self.table.setItem(row, 1, QTableWidgetItem(status))
        self.table.setItem(row, 2, QTableWidgetItem(detail))

    @staticmethod
    def _describe(row: dict[str, str]) -> str:
        return " | ".join(f"{key}: {value}" for key, value in row.items() if value)[:500]
