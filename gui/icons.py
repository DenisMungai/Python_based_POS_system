"""Tintable loader for the bundled thin-line SVG icon family."""

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from gui.styles.tokens import px

ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons"
APP_ICON_PATH = ICON_DIR / "favicon.svg"


def load_app_icon() -> QIcon:
    """Load the bundled POS icon used by the desktop application."""
    if not APP_ICON_PATH.is_file():
        raise FileNotFoundError(f"Application icon is missing: {APP_ICON_PATH}")
    icon = QIcon(str(APP_ICON_PATH))
    if icon.isNull():
        raise RuntimeError(f"Qt could not load the application icon: {APP_ICON_PATH}")
    return icon


def load_icon(name: str, color: str, size: int = 20) -> QIcon:
    """Load and recolor one bundled SVG icon at a scaled design size."""
    path = ICON_DIR / f"{name}.svg"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown bundled icon: {name}")
    svg = path.read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError(f"Bundled icon is not valid SVG: {path.name}")
    dimension = px(size)
    pixmap = QPixmap(dimension, dimension)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
