"""Qt application setup and bridge from backend events to GUI signals."""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from backend.bootstrap import AppContext
from backend.core.events import Event
from gui.icons import load_app_icon
from gui.i18n import configure_terminology
from gui.styles.fonts import fpx, ui_font_family
from gui.styles.qss import build_stylesheet
from gui.styles.tokens import (
    DEFAULT_PALETTE, PALETTES, Palette, configure_ui_scale, set_active_palette,
)

LOGGER = logging.getLogger(__name__)


def load_ui_font() -> QFont:
    """Return the application font using an installed system family."""
    font = QFont(ui_font_family())
    font.setPixelSize(fpx("body"))
    return font


class EventBusBridge(QObject):
    """Translate backend events into thread-safe Qt signals."""

    event_received = Signal(str, object)

    def __init__(self, context: AppContext, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._unsubscribers = [
            context.events.subscribe(event_name, self._publish)
            for event_name in (
                "stock_changed", "sale_completed", "low_stock_alert",
                "settings_changed", "terminology_changed", "catalog_changed",
            )
        ]

    def _publish(self, event: Event) -> None:
        """Forward an event's name and immutable payload to Qt."""
        self.event_received.emit(event.name, dict(event.payload))

    def unsubscribe(self) -> None:
        """Unsubscribe the bridge from all backend events."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()


def create_application(
    context: AppContext, argv: list[str] | None = None, palette: Palette | None = None
) -> tuple[QApplication, EventBusBridge]:
    """Create the QApplication, load configured font styling, and bridge events."""
    application = QApplication.instance() or QApplication(argv or [])
    application.setApplicationName("Inventory and POS")
    application.setWindowIcon(load_app_icon())
    screen = application.primaryScreen()
    if screen is None:
        raise RuntimeError("Qt could not identify a primary display.")
    configure_ui_scale(screen.devicePixelRatio())
    application.setFont(load_ui_font())
    selected_palette = palette or PALETTES.get(
        context.settings.get("accent_palette", DEFAULT_PALETTE.name) or "",
        DEFAULT_PALETTE,
    )
    set_active_palette(selected_palette)
    application.setStyleSheet(build_stylesheet(selected_palette))
    configure_terminology(context.settings)
    bridge = EventBusBridge(context)
    return application, bridge
