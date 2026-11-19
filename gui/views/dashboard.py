"""Service-backed dashboard with a live point-of-sale workspace."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QScrollArea,
    QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.money import fmt, milli_to_qty
from gui.i18n import t
from gui.styles.tokens import px
from gui.views.current_sale import CurrentSaleView
from gui.widgets import KpiCard, StatusPill


class DashboardView(QWidget):
    """Show live business metrics, checkout, and inventory alerts."""

    sale_completed = Signal(object)

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(px(28), px(20), px(28), px(24))
        self.layout.setSpacing(px(14))
        self.kpi_grid = QHBoxLayout()
        self.kpi_grid.setSpacing(px(12))
        self.layout.addLayout(self.kpi_grid)

        self.current_sale = CurrentSaleView(context)
        self.current_sale.sale_completed.connect(self.sale_completed.emit)
        self.layout.addWidget(self.current_sale, 1)

        alerts = QFrame()
        alerts.setProperty("card", True)
        alerts_layout = QVBoxLayout(alerts)
        alerts_layout.setContentsMargins(px(16), px(12), px(16), px(12))
        alerts_layout.setSpacing(px(6))
        self.stock_heading = QLabel(t("low_stock", "Low-stock alerts"))
        self.stock_heading.setObjectName("drawerTitle")
        alerts_layout.addWidget(self.stock_heading)
        self.stock_list = QVBoxLayout()
        self.stock_list.setSpacing(px(2))
        alerts_layout.addLayout(self.stock_list)
        self.layout.addWidget(alerts)
        self.layout.addStretch(1)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        self.refresh()

    def focus_search(self) -> None:
        """Focus the dashboard catalogue search for keyboard checkout."""
        self.current_sale.focus_search()

    def refresh(self) -> None:
        """Reload authorized dashboard and inventory service data."""
        metrics = self.context.reports.dashboard_kpis()
        currency = self.context.settings.get("currency")
        if not currency:
            raise RuntimeError("The business currency is not configured.")
        cards = (
            (t("sales_today", "Sales today"), fmt(metrics["sales_minor"], currency), ""),
            (t("orders_today", "Orders"), str(metrics["orders"]), ""),
            (t("customers", "Customers"), str(metrics["customers"]), ""),
            (t("average_order", "Average order"), fmt(metrics["average_order_minor"], currency), ""),
        )
        while self.kpi_grid.count():
            item = self.kpi_grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        for title, value, delta in cards:
            card = KpiCard(title, value, delta)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.kpi_grid.addWidget(card, 1)

        while self.stock_list.count():
            item = self.stock_list.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        low_stock = self.context.inventory.low_stock_items()
        if not low_stock:
            empty = QLabel(t("no_low_stock", "All tracked items are above their low-stock threshold."))
            empty.setObjectName("mutedText")
            self.stock_list.addWidget(empty)
            return
        for row in low_stock[:3]:
            line = QWidget()
            line_layout = QGridLayout(line)
            line_layout.setContentsMargins(0, px(3), 0, px(3))
            line_layout.setColumnStretch(0, 1)
            name = QLabel(str(row["name"]))
            quantity = QLabel(f"{milli_to_qty(int(row['stock_milli'])):g} {row.get('unit') or ''}".strip())
            line_layout.addWidget(name, 0, 0)
            line_layout.addWidget(quantity, 0, 1)
            line_layout.addWidget(StatusPill(t("low", "Low")), 0, 2)
            self.stock_list.addWidget(line)
