"""Primary desktop shell for the signed-in POS workflow."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.errors import PermissionDeniedError, PosError
from backend.models.records import SaleResult
from gui.app import EventBusBridge
from gui.dialogs.profile import ProfileDialog
from gui.dialogs.sale_complete import SaleCompleteDialog
from gui.i18n import t
from gui.icons import load_icon
from gui.styles.qss import build_stylesheet
from gui.styles.tokens import DEFAULT_PALETTE, PALETTES, Palette, px
from gui.views.current_sale import CurrentSaleView
from gui.views.dashboard import DashboardView
from gui.views.products import ProductsView
from gui.views.operations import CustomersView, DiscountsView, OrdersView, ReturnsView, SalesView
from gui.views.admin import ReportsView, SettingsView, UsersView
from gui.widgets import SidebarNavItem


class AppWindow(QMainWindow):
    """Signed-in window with dashboard and a complete current-sale route."""

    logout_requested = Signal()

    def __init__(
        self, context: AppContext, bridge: EventBusBridge,
        palette: Palette | None = None,
    ) -> None:
        super().__init__()
        self.context = context
        self.bridge = bridge
        self.palette = palette or PALETTES.get(
            context.settings.get("accent_palette", DEFAULT_PALETTE.name) or "",
            DEFAULT_PALETTE,
        )
        user = context.auth.current_user
        if user is None:
            raise RuntimeError("The application shell requires an authenticated user.")
        business = context.settings.get("business_name", "POS") or "POS"
        sale_term = context.settings.term("sale", "Sale")
        self.setWindowTitle(f"{business} {sale_term}")
        application = QApplication.instance()
        if application is not None:
            self.setWindowIcon(application.windowIcon())
        self.setMinimumSize(px(1280), px(760))

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setProperty("sidebar", True)
        sidebar.setFixedWidth(px(232))
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(px(18), px(22), px(18), px(18))
        sidebar_layout.setSpacing(px(2))
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(px(9))
        mark = QLabel(business[:1].upper() or "P")
        mark.setObjectName("businessMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(px(30), px(30))
        brand_row.addWidget(mark)
        brand = QLabel(business)
        self.brand_label = brand
        brand.setWordWrap(True)
        brand.setStyleSheet(f"font-size: {px(18)}px; font-weight: 600;")
        brand_row.addWidget(brand, 1)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(px(8))
        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("navScroll")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_page = QWidget()
        nav_layout = QVBoxLayout(nav_page)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(px(2))
        nav_scroll.setWidget(nav_page)
        sidebar_layout.addWidget(nav_scroll, 1)

        self.stack = QStackedWidget()
        self.routes: dict[str, QWidget] = {}
        self.navigation: dict[str, SidebarNavItem] = {}
        try:
            context.auth.require_permission("reports.read")
        except PermissionDeniedError:
            pass
        else:
            dashboard = DashboardView(context)
            dashboard.sale_completed.connect(self._show_receipt)
            self._add_route(nav_layout, "dashboard", t("dashboard", "Dashboard"), "dashboard", dashboard)

        sale_view = CurrentSaleView(context)
        sale_view.sale_completed.connect(self._show_receipt)
        self._add_route(nav_layout, "sales", sale_term, "sales", sale_view)

        try:
            context.auth.require_permission("sales.process")
        except PermissionDeniedError:
            pass
        else:
            orders = OrdersView(context)
            orders.recall_requested.connect(self._recall_held)
            self._add_route(nav_layout, "orders", t("orders", "Orders"), "sales", orders)

        try:
            context.auth.require_permission("catalog.read")
        except PermissionDeniedError:
            pass
        else:
            products = ProductsView(context)
            self._add_route(
                nav_layout, "products",
                context.settings.term("item_plural", t("products", "Products")),
                "catalog", products,
            )

        try:
            context.auth.require_permission("customers.read")
        except PermissionDeniedError:
            pass
        else:
            self._add_route(
                nav_layout, "customers",
                context.settings.term("customer_plural", t("customers", "Customers")),
                "customer", CustomersView(context),
            )

        try:
            context.auth.require_permission("sales.read")
        except PermissionDeniedError:
            pass
        else:
            self._add_route(
                nav_layout, "sales_history", t("sales_history", "Sales history"),
                "sales", SalesView(context),
            )

        try:
            context.auth.require_permission("sales.return")
        except PermissionDeniedError:
            pass
        else:
            self._add_route(
                nav_layout, "returns", t("returns", "Returns"),
                "sales", ReturnsView(context),
            )

        try:
            context.auth.require_permission("discounts.write")
        except PermissionDeniedError:
            pass
        else:
            self._add_route(
                nav_layout, "discounts", t("discounts", "Discounts"),
                "sales", DiscountsView(context),
            )

        try:
            context.auth.require_permission("reports.read")
        except PermissionDeniedError:
            pass
        else:
            self._add_route(
                nav_layout, "reports", t("reports", "Reports"),
                "dashboard", ReportsView(context),
            )

        try:
            context.auth.require_permission("users.manage")
        except PermissionDeniedError:
            pass
        else:
            self._add_route(
                nav_layout, "users", t("users", "Users"),
                "customer", UsersView(context),
            )
            self._add_route(
                nav_layout, "settings", t("settings", "Settings"),
                "dashboard", SettingsView(context),
            )

        self.user_name_label = QLabel(user.display_name)
        self.user_name_label.setContentsMargins(px(24), 0, 0, 0)
        sidebar_layout.addWidget(self.user_name_label)
        role = QLabel(user.role)
        role.setContentsMargins(px(24), 0, 0, 0)
        role.setStyleSheet(f"font-size: {px(12)}px;")
        sidebar_layout.addWidget(role)
        if user.role == "Admin":
            profile = QPushButton(t("my_profile", "My profile"))
            profile.setIcon(load_icon("customer", self.palette.on_primary, 18))
            profile.setIconSize(QSize(px(18), px(18)))
            profile.clicked.connect(self._edit_profile)
            sidebar_layout.addWidget(profile)
        logout = QPushButton(t("log_out", "Log out"))
        logout.setIcon(load_icon("logout", self.palette.on_primary, 18))
        logout.setIconSize(QSize(px(18), px(18)))
        logout.clicked.connect(self._logout)
        sidebar_layout.addWidget(logout)

        root_layout.addWidget(sidebar)
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        root_layout.addLayout(content, 1)
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(px(24), px(36), px(24), px(18))
        topbar_layout.setSpacing(px(12))
        welcome = QFrame()
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.setContentsMargins(0, 0, 0, 0)
        welcome_layout.setSpacing(px(2))
        welcome_title = QLabel(f"{t('welcome_back', 'Welcome back')}, {user.display_name}!")
        self.welcome_title = welcome_title
        welcome_title.setObjectName("welcomeTitle")
        welcome_layout.addWidget(welcome_title)
        welcome_detail = QLabel(f"{t('today_activity', 'Here is what is happening today')} · {business}")
        self.welcome_detail_label = welcome_detail
        welcome_detail.setObjectName("mutedText")
        welcome_layout.addWidget(welcome_detail)
        topbar_layout.addWidget(welcome, 1)
        self.topbar_brand = QLabel(business)
        self.topbar_brand.hide()
        topbar_layout.addWidget(self.topbar_brand)
        global_search = QLineEdit()
        global_search.setObjectName("globalSearch")
        global_search.setPlaceholderText(t("search_anything", "Search anything"))
        global_search.setFixedWidth(px(245))
        global_search.textChanged.connect(self._global_search)
        topbar_layout.addWidget(global_search)
        content.addWidget(topbar)
        content.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.bridge.event_received.connect(self._on_backend_event)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._focus_sale_search)
        QShortcut(QKeySequence("F2"), self).activated.connect(self._focus_sale_search)

        if "dashboard" in self.navigation:
            self._navigate("dashboard")
        else:
            self._navigate("sales")

    def _add_route(
        self, sidebar_layout: QVBoxLayout, route: str, label: str,
        icon: str, view: QWidget,
    ) -> None:
        nav = SidebarNavItem(route, label, icon, palette=self.palette)
        nav.setToolTip(label)
        nav.setAccessibleName(label)
        nav.setFixedHeight(px(44))
        nav.navigation_requested.connect(self._navigate)
        sidebar_layout.addWidget(nav)
        self.navigation[route] = nav
        self.routes[route] = view
        self.stack.addWidget(view)

    def _navigate(self, route: str) -> None:
        view = self.routes.get(route)
        if view is None:
            return
        self.stack.setCurrentWidget(view)
        if route in {"dashboard", "sales"}:
            sale_view = view.current_sale if isinstance(view, DashboardView) else view
            if isinstance(sale_view, CurrentSaleView):
                sale_view.refresh_catalog()
        if route == "orders" and isinstance(view, OrdersView):
            view.refresh()
        if isinstance(
            view,
            (ProductsView, CustomersView, SalesView, ReturnsView, DiscountsView, ReportsView, UsersView),
        ):
            view.refresh()
        for key, nav in self.navigation.items():
            nav.set_active(key == route)

    def _focus_sale_search(self) -> None:
        self._navigate("sales")
        sale_view = self.routes["sales"]
        if isinstance(sale_view, CurrentSaleView):
            sale_view.focus_search()

    def _global_search(self, text: str) -> None:
        self._navigate("sales")
        sale_view = self.routes["sales"]
        if isinstance(sale_view, CurrentSaleView):
            sale_view.search.setText(text)

    def _show_receipt(self, result: object) -> None:
        if not isinstance(result, SaleResult):
            raise TypeError("Sale completion signal must provide a SaleResult.")
        dashboard = self.routes.get("dashboard")
        if isinstance(dashboard, DashboardView):
            dashboard.refresh()
        SaleCompleteDialog(self.context, result).exec()

    def _recall_held(self, held: object) -> None:
        if not isinstance(held, dict) or not isinstance(held.get("lines"), list):
            return
        sale_view = self.routes.get("sales")
        if not isinstance(sale_view, CurrentSaleView):
            return
        if not sale_view.load_sale_lines(held["lines"]):
            return
        try:
            self.context.sales.recall_held(int(held["id"]), remove=True)
        except PosError as error:
            sale_view.toast.show_message(error.message)
        orders = self.routes.get("orders")
        if isinstance(orders, OrdersView):
            orders.refresh()
        self._navigate("sales")

    def _on_backend_event(self, name: str, payload: object) -> None:
        if name == "settings_changed":
            business = self.context.settings.get("business_name", "POS") or "POS"
            self.brand_label.setText(business)
            mark = self.findChild(QLabel, "businessMark")
            if mark is not None:
                mark.setText(business[:1].upper() or "P")
            self.topbar_brand.setText(business)
            palette_name = self.context.settings.get("accent_palette", DEFAULT_PALETTE.name)
            palette = PALETTES.get(palette_name or "", DEFAULT_PALETTE)
            self.palette = palette
            application = QApplication.instance()
            if application is not None:
                application.setStyleSheet(build_stylesheet(palette))
            icon_by_route = {
                "dashboard": "dashboard", "products": "catalog", "customers": "customer",
                "sales_history": "sales", "orders": "sales", "returns": "sales", "discounts": "sales",
                "reports": "dashboard", "users": "customer", "settings": "dashboard",
                "sales": "sales",
            }
            for route, nav in self.navigation.items():
                nav.icon_name = icon_by_route[route]
                nav.palette = palette
                nav.setIcon(load_icon(
                    nav.icon_name,
                    palette.primary if nav.property("active") else palette.on_primary,
                    18,
                ))
            setting_key = payload.get("key") if isinstance(payload, dict) else None
            if setting_key == "business_name":
                self.setWindowTitle(f"{business} {self.context.settings.term('sale', 'Sale')}")
        if name in {"catalog_changed", "stock_changed"}:
            for view in self.routes.values():
                if isinstance(view, CurrentSaleView):
                    view.refresh_catalog()
                elif isinstance(view, DashboardView):
                    view.current_sale.refresh_catalog()
                elif isinstance(view, ProductsView):
                    view.refresh()
        if name not in {"sale_completed", "stock_changed"}:
            return
        dashboard = self.routes.get("dashboard")
        if isinstance(dashboard, DashboardView):
            dashboard.refresh()

    def _logout(self) -> None:
        self.context.auth.logout()
        self.logout_requested.emit()
        self.close()

    def _edit_profile(self) -> None:
        if ProfileDialog(self.context, self).exec() != ProfileDialog.DialogCode.Accepted:
            return
        user = self.context.auth.current_user
        if user is not None:
            self.user_name_label.setText(user.display_name)
            self.welcome_title.setText(f"{t('welcome_back', 'Welcome back')}, {user.display_name}!")

