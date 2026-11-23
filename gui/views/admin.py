"""Reports, user administration, and settings views."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.errors import PosError
from backend.core.money import fmt, milli_to_qty
from gui.i18n import t
from gui.styles.fonts import fpx
from gui.styles.qss import build_stylesheet
from gui.styles.tokens import DEFAULT_PALETTE, PALETTES, px
from gui.widgets import (
    KpiCard, ModuleToggleRow, Toast, apply_card_elevation, clear_table_widgets,
    configure_table,
)


class SalesSeriesChart(QWidget):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color = QColor(color)
        self.series: list[dict[str, Any]] = []
        self.setMinimumHeight(px(150))

    def set_series(self, series: list[dict[str, Any]]) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        event.accept()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.rect().adjusted(px(38), px(12), -px(12), -px(30))
        painter.setPen(QPen(QColor("#D7E0E2"), px(1)))
        painter.drawLine(bounds.bottomLeft(), bounds.bottomRight())
        if not self.series:
            painter.setPen(QColor("#64748B"))
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, t("no_sales", "No sales in this period"))
            return
        maximum = max(int(row["sales_minor"]) for row in self.series) or 1
        slot = bounds.width() / len(self.series)
        bar_width = min(px(28), slot * 0.58)
        painter.setBrush(self.color)
        painter.setPen(Qt.PenStyle.NoPen)
        for index, row in enumerate(self.series):
            height = bounds.height() * int(row["sales_minor"]) / maximum
            left = bounds.left() + slot * index + (slot - bar_width) / 2
            painter.drawRoundedRect(
                int(left), int(bounds.bottom() - height), int(bar_width),
                max(px(2), int(height)), px(3), px(3),
            )
        painter.setPen(QColor("#64748B"))
        font = self.font()
        font.setPixelSize(fpx("caption"))
        painter.setFont(font)
        first = str(self.series[0].get("day", ""))
        last = str(self.series[-1].get("day", ""))
        label_top = bounds.bottom() + px(3)
        painter.drawText(
            px(38), label_top, max(px(80), bounds.width() // 3), px(18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, first,
        )
        painter.drawText(
            self.width() - px(92), label_top, px(80), px(18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, last,
        )


class ReportsView(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context, self.currency = context, context.settings.get("currency") or "KES"
        self.toast = Toast(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(10))
        heading = QLabel(t("reports", "Reports"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        controls = QHBoxLayout()
        self.period = QComboBox()
        self.period.addItem(t("date_range", "Date range"), "range")
        self.period.addItem(t("daily_report", "Daily"), "daily")
        self.period.addItem(t("weekly_report", "Weekly"), "weekly")
        self.period.addItem(t("monthly_report", "Monthly"), "monthly")
        self.period.currentIndexChanged.connect(self._period_changed)
        controls.addWidget(self.period)
        self.start = QLineEdit(date.today().replace(day=1).isoformat())
        self.start.setPlaceholderText(t("start_date", "Start date (YYYY-MM-DD)"))
        self.end = QLineEdit(date.today().isoformat())
        self.end.setPlaceholderText(t("end_date", "End date (YYYY-MM-DD)"))
        self.start_label = QLabel(t("start", "Start"))
        self.end_label = QLabel(t("end", "End"))
        controls.addWidget(self.start_label)
        controls.addWidget(self.start)
        controls.addWidget(self.end_label)
        controls.addWidget(self.end)
        self.start.editingFinished.connect(self._period_changed)
        refresh = QPushButton(t("refresh", "Refresh"))
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        export = QPushButton(t("export_csv", "Export CSV"))
        export.setProperty("primary", True)
        export.clicked.connect(self._export)
        controls.addWidget(export)
        layout.addLayout(controls)
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(px(10))
        layout.addLayout(self.kpi_grid)
        palette_name = context.settings.get("accent_palette", DEFAULT_PALETTE.name) or DEFAULT_PALETTE.name
        palette = PALETTES.get(palette_name, DEFAULT_PALETTE)
        self.chart = SalesSeriesChart(palette.primary)
        self.chart.setProperty("card", True)
        layout.addWidget(self.chart)
        tables = QHBoxLayout()
        self.table = QTableWidget(0, 3)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("top_items", "Top items"), t("quantity", "Quantity"), t("sales", "Sales"),
        ])
        self.breakdown_table = QTableWidget(0, 3)
        configure_table(self.breakdown_table)
        self.breakdown_table.setHorizontalHeaderLabels([
            t("category", "Type"), t("name", "Payment / item"), t("sales", "Sales"),
        ])
        tables.addWidget(self.table, 1)
        tables.addWidget(self.breakdown_table, 1)
        layout.addLayout(tables, 1)
        self._period_changed()
        self.refresh()

    def _period_changed(self) -> None:
        period = self.period.currentData()
        is_range = period == "range"
        self.end.setEnabled(is_range)
        if period == "weekly":
            self.start_label.setText(t("week_containing", "Week containing"))
            self.end_label.setText(t("week_ends", "Week ends"))
            try:
                selected = date.fromisoformat(self.start.text().strip())
            except ValueError:
                return
            week_start = selected - timedelta(days=selected.weekday())
            self.end.setText((week_start + timedelta(days=6)).isoformat())
        else:
            self.start_label.setText(t("start", "Start"))
            self.end_label.setText(t("end", "End"))

    def _bounds(self) -> tuple[date, datetime, datetime]:
        selected_start = date.fromisoformat(self.start.text().strip())
        period = self.period.currentData()
        if period == "weekly":
            start_day = selected_start - timedelta(days=selected_start.weekday())
            end_day = start_day + timedelta(days=6)
        else:
            start_day = selected_start
            end_day = (
                date.fromisoformat(self.end.text().strip())
                if period == "range" else start_day
            )
        if end_day < start_day:
            raise ValueError("The end date must not be before the start date.")
        start_at = datetime.combine(start_day, time.min, timezone.utc)
        end_at = datetime.combine(end_day + timedelta(days=1), time.min, timezone.utc)
        return start_day, start_at, end_at

    def refresh(self) -> None:
        try:
            start_day, start_at, end_at = self._bounds()
            period = self.period.currentData()
            if period == "daily":
                report = self.context.reports.daily_report(start_day.isoformat())
                report["item_types"] = self.context.reports.breakdowns(
                    start_at.isoformat(), end_at.isoformat(),
                )["item_types"]
                series = self.context.reports.sales_series(
                    start_at.isoformat(), end_at.isoformat(),
                )
            elif period == "monthly":
                report = self.context.reports.monthly_report(start_day.year, start_day.month)
                month_start = datetime(start_day.year, start_day.month, 1, tzinfo=timezone.utc)
                next_month = datetime(
                    start_day.year + (start_day.month == 12),
                    start_day.month % 12 + 1, 1, tzinfo=timezone.utc,
                )
                breakdown = self.context.reports.breakdowns(
                    month_start.isoformat(), next_month.isoformat(),
                )
                report["payments"] = breakdown["payments"]
                report["item_types"] = breakdown["item_types"]
                series = report["series"]
                start_at, end_at = month_start, next_month
            else:
                report = self.context.reports.range_report(
                    start_at.isoformat(), end_at.isoformat(),
                )
                series = report["series"]
            top = self.context.reports.top_items(
                start_at.isoformat(), end_at.isoformat(), limit=20,
            )
            valuation = self.context.reports.stock_valuation()
        except PosError as error:
            self.toast.show_message(error.message)
            return
        except ValueError as error:
            self.toast.show_message(str(error) or t("invalid_report_dates", "Enter valid report dates."))
            return

        while self.kpi_grid.count():
            item = self.kpi_grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        cards = (
            (t("period_sales", "Sales"), fmt(int(report["sales_minor"]), self.currency)),
            (t("orders", "Orders"), str(report["orders"])),
            (t("stock_cost", "Stock cost"), fmt(int(valuation["cost_minor"]), self.currency)),
            (t("stock_retail", "Stock retail"), fmt(int(valuation["retail_minor"]), self.currency)),
        )
        for index, card in enumerate(cards):
            self.kpi_grid.addWidget(KpiCard(*card), 0, index)
        self.chart.set_series(series)
        self.table.setRowCount(len(top))
        for row, item in enumerate(top):
            values = (
                str(item["name"]),
                str(milli_to_qty(int(item["quantity_milli"]))),
                fmt(int(item["total_minor"]), self.currency),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        breakdown_rows = [
            (t("payment", "Payment"), str(row["method"]), int(row["amount_minor"]))
            for row in report.get("payments", [])
        ]
        breakdown_rows.extend(
            (
                t("item_type", "Item type"),
                f"{row['item_type']} ({milli_to_qty(int(row['quantity_milli'])):g})",
                int(row["total_minor"]),
            )
            for row in report.get("item_types", [])
        )
        self.breakdown_table.setRowCount(len(breakdown_rows))
        for row, values in enumerate(breakdown_rows):
            cells = (values[0], values[1], fmt(values[2], self.currency))
            for column, value in enumerate(cells):
                self.breakdown_table.setItem(row, column, QTableWidgetItem(value))

    def _export(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, t("export_sales", "Export sales"), "sales.csv", "CSV files (*.csv)",
        )
        if not selected:
            return
        try:
            _, start_at, end_at = self._bounds()
            path = self.context.reports.export_sales_csv(
                start_at.isoformat(), end_at.isoformat(), Path(selected),
            )
            self.toast.show_message(t("export_complete", "Export complete.") + f" {path.name}")
        except PosError as error:
            self.toast.show_message(error.message)
        except ValueError as error:
            self.toast.show_message(str(error) or t("invalid_report_dates", "Enter valid report dates."))


class UserDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(t("add_user", "Add user"))
        self.setModal(True)
        self.setMinimumWidth(px(460))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(24), px(22), px(24), px(22))
        form = QFormLayout()
        self.username = QLineEdit()
        self.display_name = QLineEdit()
        self.role = QComboBox()
        self.role.addItems(["Admin", "Manager", "Cashier"])
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("username", "Username"), self.username)
        form.addRow(t("display_name", "Display name"), self.display_name)
        form.addRow(t("role", "Role"), self.role)
        form.addRow(t("password", "Password"), self.password)
        layout.addLayout(form)
        self.error = QLabel()
        self.error.setObjectName("errorMessage")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        actions = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(t("create", "Create"))
        save.setProperty("primary", True)
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _save(self) -> None:
        try:
            self.context.auth.create_user(
                self.username.text(), self.display_name.text(),
                self.role.currentText(), self.password.text(),
            )
        except PosError as error:
            self.error.setText(error.message)
            self.error.show()
            return
        self.accept()


class UsersView(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(12))
        heading = QLabel(t("users", "Users"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        add = QPushButton(t("add_user", "Add user"))
        add.setProperty("primary", True)
        add.clicked.connect(lambda: UserDialog(context, self).exec() and self.refresh())
        toolbar.addWidget(add)
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, 5)
        configure_table(self.table)
        self.table.setHorizontalHeaderLabels([
            t("username", "Username"), t("display_name", "Display name"),
            t("role", "Role"), t("active", "Active"), t("actions", "Actions"),
        ])
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        users = self.context.auth.list_users()
        clear_table_widgets(self.table)
        self.table.setRowCount(len(users))
        for row, user in enumerate(users):
            values = (
                str(user["username"]), str(user["display_name"]), str(user["role"]),
                t("yes", "Yes") if user["active"] else t("no", "No"),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            active = QCheckBox(t("active", "Active"))
            active.setChecked(bool(user["active"]))
            active.toggled.connect(
                lambda checked, item=user: self._set_active(item, checked)
            )
            action_layout.addWidget(active)
            self.table.setCellWidget(row, 4, actions)

    def _set_active(self, user: dict[str, Any], active: bool) -> None:
        try:
            self.context.auth.update_user(int(user["id"]), active=int(active))
        except PosError as error:
            Toast(self).show_message(error.message)
            self.refresh()


class SettingsView(QWidget):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context, self.toast = context, Toast(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(18), px(28), px(18))
        layout.setSpacing(px(10))
        heading = QLabel(t("settings", "Settings"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)

        subtitle = QLabel(t("settings_description", "Manage your business profile, checkout options, and local data."))
        subtitle.setObjectName("mutedText")
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        profile_scroll, profile_layout = self._scroll_page()
        self.tabs.addTab(profile_scroll, t("business_profile", "Business profile"))
        profile_card, profile_card_layout = self._settings_card(
            t("business_details", "Business details"),
            t("business_details_help", "These details appear across the application and receipts."),
        )
        form = QFormLayout()
        form.setContentsMargins(0, px(12), 0, 0)
        form.setSpacing(px(12))
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.business_name = QLineEdit(context.settings.get("business_name", "") or "")
        self.currency = QLineEdit(context.settings.get("currency", "") or "")
        self.currency.setMaxLength(3)
        self.currency.setPlaceholderText(t("currency_code", "Three-letter code"))
        self.palette = QComboBox()
        self.palette.addItems(PALETTES)
        current_palette = context.settings.get("accent_palette", DEFAULT_PALETTE.name)
        self.palette.setCurrentText(current_palette if current_palette in PALETTES else DEFAULT_PALETTE.name)
        self.tax_name = QLineEdit()
        self.tax_rate = QLineEdit()
        rates = context.settings.tax_rates()
        default_rate = next((rate for rate in rates if rate["is_default"]), rates[0] if rates else None)
        self.tax_name.setText(str(default_rate["name"]) if default_rate else t("standard_tax", "Standard tax"))
        self.tax_rate.setText(
            str(Decimal(int(default_rate["rate_basis_points"])) / Decimal(100)) if default_rate else "0"
        )
        form.addRow(t("business_name", "Business name"), self.business_name)
        form.addRow(t("currency", "Currency"), self.currency)
        form.addRow(t("accent_palette", "Accent palette"), self.palette)
        profile_card_layout.addLayout(form)
        profile_layout.addWidget(profile_card)

        tax_card, tax_layout = self._settings_card(
            t("tax_settings", "Default tax"),
            t("tax_settings_help", "Set the default tax rate used for new catalogue items."),
        )
        tax_form = QFormLayout()
        tax_form.setContentsMargins(0, px(12), 0, 0)
        tax_form.setSpacing(px(12))
        tax_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tax_form.addRow(t("default_tax", "Tax name"), self.tax_name)
        tax_form.addRow(t("tax_rate_percent", "Tax rate (%)"), self.tax_rate)
        tax_layout.addLayout(tax_form)
        profile_layout.addWidget(tax_card)
        profile_layout.addStretch(1)

        options_scroll, options_layout = self._scroll_page()
        self.tabs.addTab(options_scroll, t("checkout_options", "Checkout options"))
        options_grid = QGridLayout()
        options_grid.setContentsMargins(0, 0, 0, 0)
        options_grid.setSpacing(px(14))
        options_layout.addLayout(options_grid)
        modules_card, modules_layout = self._settings_card(
            t("modules", "Feature modules"),
            t("modules_help", "Turn on additional tools for your business."),
        )
        self.module_rows: list[ModuleToggleRow] = []
        for key, enabled in context.settings.modules().items():
            row = ModuleToggleRow(key, key.replace("_", " ").title(), enabled)
            row.module_changed.connect(self._module_changed)
            self.module_rows.append(row)
            modules_layout.addWidget(row)
        payment_card, payment_layout = self._settings_card(
            t("payment_methods", "Payment methods"),
            t("payment_methods_help", "Choose which payment methods appear at checkout."),
        )
        self.payment_checks: dict[str, QCheckBox] = {}
        active_methods = {
            str(row["name"]): True for row in context.settings.payment_methods()
        }
        payments_grid = QGridLayout()
        payments_grid.setContentsMargins(0, px(12), 0, 0)
        payments_grid.setHorizontalSpacing(px(20))
        payments_grid.setVerticalSpacing(px(12))
        payments_grid.setRowStretch(2, 1)
        for name in ("Cash", "Card", "M-Pesa", "Bank transfer"):
            check = QCheckBox(name)
            check.setChecked(active_methods.get(name, False))
            check.toggled.connect(self._payment_changed)
            self.payment_checks[name] = check
            index = len(self.payment_checks) - 1
            payments_grid.addWidget(check, index // 2, index % 2)
        payment_layout.addLayout(payments_grid)
        options_grid.addWidget(modules_card, 0, 0)
        options_grid.addWidget(payment_card, 0, 1)
        options_grid.setColumnStretch(0, 3)
        options_grid.setColumnStretch(1, 2)
        options_layout.addStretch(1)

        data_scroll, data_layout = self._scroll_page()
        self.tabs.addTab(data_scroll, t("data_and_backups", "Data and backups"))
        backup_card, backup_card_layout = self._settings_card(
            t("backups", "Backups"),
            t("backup_help", "Create a local backup or restore one saved on this device."),
        )
        backup_actions = QHBoxLayout()
        backup = QPushButton(t("create_backup", "Create backup"))
        backup.setProperty("primary", True)
        backup.clicked.connect(self._backup)
        backup_actions.addWidget(backup)
        backup_card_layout.addLayout(backup_actions)
        restore_heading = QLabel(t("restore_backup", "Restore a backup"))
        restore_heading.setObjectName("sectionTitle")
        backup_card_layout.addWidget(restore_heading)
        restore_row = QHBoxLayout()
        self.backup_list = QComboBox()
        self._refresh_backups()
        restore_row.addWidget(self.backup_list, 1)
        restore = QPushButton(t("restore", "Restore"))
        restore.clicked.connect(self._restore_backup)
        restore_row.addWidget(restore)
        backup_card_layout.addLayout(restore_row)
        data_layout.addWidget(backup_card)
        data_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        save = QPushButton(t("save", "Save"))
        save.setProperty("primary", True)
        save.clicked.connect(self._save_profile)
        actions.addWidget(save, 0)
        layout.addLayout(actions)

    @staticmethod
    def _scroll_page() -> tuple[QScrollArea, QVBoxLayout]:
        """Create a tab page that scrolls cleanly in compact windows."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        page_layout = QVBoxLayout(content)
        page_layout.setContentsMargins(px(4), px(12), px(4), px(12))
        page_layout.setSpacing(px(14))
        scroll.setWidget(content)
        return scroll, page_layout

    @staticmethod
    def _settings_card(title: str, description: str) -> tuple[QFrame, QVBoxLayout]:
        """Build a consistent section card for settings controls."""
        card = QFrame()
        card.setProperty("settingsCard", True)
        apply_card_elevation(card)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(px(18), px(16), px(18), px(16))
        card_layout.setSpacing(px(8))
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        card_layout.addWidget(heading)
        detail = QLabel(description)
        detail.setObjectName("mutedText")
        detail.setWordWrap(True)
        card_layout.addWidget(detail)
        return card, card_layout

    def _refresh_backups(self) -> None:
        self.backup_list.clear()
        for backup in self.context.backups.list_backups():
            self.backup_list.addItem(backup.name, str(backup))
        if self.backup_list.count() == 0:
            self.backup_list.addItem(t("no_backups", "No backups available"), "")

    def _restore_backup(self) -> None:
        path_text = self.backup_list.currentData()
        if not path_text:
            self.toast.show_message(t("no_backups", "No backups available"))
            return
        confirm = QDialog(self)
        confirm.setWindowTitle(t("restore_backup", "Restore backup"))
        confirm.setModal(True)
        confirm_layout = QVBoxLayout(confirm)
        confirm_layout.setContentsMargins(px(24), px(22), px(24), px(22))
        confirm_layout.addWidget(QLabel(t(
            "restore_confirmation",
            "Restore this backup? Current database changes will be replaced.",
        )))
        buttons = QHBoxLayout()
        cancel = QPushButton(t("cancel", "Cancel"))
        cancel.clicked.connect(confirm.reject)
        proceed = QPushButton(t("restore", "Restore"))
        proceed.setProperty("primary", True)
        proceed.clicked.connect(confirm.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(proceed)
        confirm_layout.addLayout(buttons)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.context.backups.restore_backup(Path(path_text))
            self.toast.show_message(t("backup_restored", "Backup restored. Restart the application."))
        except PosError as error:
            self.toast.show_message(error.message)

    def _save_profile(self) -> None:
        try:
            rate = Decimal(self.tax_rate.text().strip()) * 100
            if rate != rate.to_integral_value() or rate < 0:
                raise ValueError
            self.context.settings.set("business_name", self.business_name.text().strip())
            self.context.settings.set("currency", self.currency.text().strip().upper())
            self.context.settings.set("accent_palette", self.palette.currentText())
            self.context.settings.set_tax_rate(
                self.tax_name.text().strip() or t("standard_tax", "Standard tax"),
                int(rate), is_default=True,
            )
        except PosError as error:
            self.toast.show_message(error.message)
            return
        except (InvalidOperation, ValueError):
            self.toast.show_message(t("invalid_tax_rate", "Enter a non-negative tax rate with up to two decimal places."))
            return
        palette = PALETTES[self.palette.currentText()]
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(build_stylesheet(palette))
        self.toast.show_message(t("settings_saved", "Settings saved."))

    def _module_changed(self, key: str, enabled: bool) -> None:
        try:
            current = self.context.settings.modules()
            current[key] = enabled
            self.context.settings.set_modules(current)
        except PosError as error:
            self.toast.show_message(error.message)

    def _payment_changed(self) -> None:
        try:
            methods = {name: check.isChecked() for name, check in self.payment_checks.items()}
            self.context.settings.set_payment_methods(methods)
        except PosError as error:
            self.toast.show_message(error.message)

    def _backup(self) -> None:
        try:
            path = self.context.backups.create_backup()
            self.toast.show_message(t("backup_created", "Backup created.") + f" {path.name}")
            self._refresh_backups()
        except PosError as error:
            self.toast.show_message(error.message)
