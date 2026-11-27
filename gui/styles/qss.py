"""Generate the shared Qt stylesheet from design tokens."""

from pathlib import Path

from PySide6.QtGui import QColor

from gui.styles.fonts import WEIGHT_MEDIUM, WEIGHT_SEMIBOLD, WEIGHT_STRONG, fpx, ui_font_family
from gui.styles.tokens import DEFAULT_PALETTE, Palette, px


def shade(color: str, factor: int) -> str:
    """Return ``color`` lightened (factor > 100) or darkened for state styling."""
    return QColor(color).lighter(factor).name().upper()


def build_stylesheet(palette: Palette = DEFAULT_PALETTE) -> str:
    """Return one scaled stylesheet for application widgets and states."""
    accent = palette.accent
    on_accent = palette.sidebar
    checkout_text = palette.checkout_text or palette.text
    checkout_hover = shade(palette.checkout, 112)
    checkout_pressed = shade(palette.checkout, 82)
    danger_hover = shade(palette.danger, 88)
    chevron_path = (
        Path(__file__).resolve().parents[2] / "assets" / "icons" / "chevron-down.svg"
    ).as_posix()
    return f"""
    QWidget {{
        background: transparent;
        color: {palette.text};
        font-family: "{ui_font_family()}";
        font-size: {fpx("body")}px;
        selection-background-color: {palette.tint};
    }}
    QMainWindow, QDialog {{ background: {palette.canvas}; }}
    QFrame#loginBrand {{
        background: {palette.sidebar};
        border: none;
    }}
    QFrame#loginBrand QLabel {{
        color: {palette.on_primary};
    }}
    QLabel#loginMark {{
        background: {palette.card};
        color: {palette.primary_text or palette.primary};
        border-radius: {px(26)}px;
        font-size: {fpx("callout")}px;
        font-weight: {WEIGHT_SEMIBOLD};
    }}
    QLabel#loginBrandName {{
        font-size: {fpx("brand")}px;
        font-weight: {WEIGHT_SEMIBOLD};
    }}
    QFrame#topbar {{
        background: {palette.canvas};
        border: none;
        min-height: {px(48)}px;
    }}
    QLabel#welcomeTitle {{ font-size: {fpx("callout")}px; font-weight: {WEIGHT_MEDIUM}; }}
    QLabel#mutedText {{ color: {palette.secondary}; font-size: {fpx("small")}px; }}
    QLineEdit#globalSearch {{
        background: {palette.card};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(11)}px;
        padding: {px(8)}px {px(12)}px;
        max-width: {px(245)}px;
    }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea#navScroll {{ background: transparent; border: none; }}
    QFrame[card="true"] {{
        background: {palette.card};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(16)}px;
    }}
    QFrame[settingsCard="true"] {{
        background: {palette.card};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(14)}px;
    }}
    QFrame[receiptPaper="true"] {{
        background: {palette.card};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(4)}px;
    }}
    QFrame[productCard="true"] {{
        background: {palette.card};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(14)}px;
    }}
    QFrame[productCard="true"]:hover {{
        border-color: {palette.primary_text or palette.primary}; background: {palette.card};
    }}
    QFrame[productCard="true"]:pressed {{
        background: {palette.tint};
    }}
    QFrame[productCard="true"][selected="true"] {{
        border-color: {palette.primary_text or palette.primary};
        border-width: {px(2)}px;
        background: {palette.card};
    }}
    QFrame[productCard="true"][inStock="false"] {{
        border-color: {palette.border}; background: {palette.canvas};
    }}
    QFrame[productCard="true"][inStock="false"]:hover {{
        border-color: {palette.border}; background: {palette.canvas};
    }}
    QLabel#sectionTitle {{ font-size: {fpx("section")}px; font-weight: {WEIGHT_SEMIBOLD}; }}
    QTabWidget::pane {{
        background: transparent; border: none; top: {px(-1)}px;
    }}
    QTabBar::tab {{
        background: transparent; color: {palette.secondary};
        border: {px(1)}px solid transparent;
        border-bottom: {px(2)}px solid transparent;
        padding: {px(9)}px {px(14)}px;
        margin-right: {px(5)}px;
        border-top-left-radius: {px(9)}px; border-top-right-radius: {px(9)}px;
    }}
    QTabBar::tab:selected {{
        background: {palette.card}; color: {palette.primary_text or palette.primary};
        border-color: {palette.border}; border-bottom-color: {palette.primary};
        font-weight: {WEIGHT_SEMIBOLD};
    }}
    QTabBar::tab:hover:!selected {{ background: {palette.tint}; }}
    QTabBar::tab:focus {{ border: {px(2)}px solid {palette.primary}; }}
    QFrame[sidebar="true"] {{
        background: {palette.sidebar};
        border: none;
        border-radius: 0;
    }}
    QFrame[sidebar="true"] QLabel {{ color: {palette.sidebar_text}; }}
    QLabel#businessMark {{
        background: {accent}; color: {on_accent};
        border-radius: {px(9)}px; font-size: {fpx("sidebar_brand")}px; font-weight: {WEIGHT_MEDIUM};
    }}
    QLabel#sidebarBrand {{
        font-size: {fpx("sidebar_brand")}px; font-weight: {WEIGHT_MEDIUM};
        color: {palette.sidebar_text};
    }}
    QFrame#sidebarDivider {{
        background: {palette.sidebar_border}; border: none;
        min-height: {px(1)}px; max-height: {px(1)}px;
    }}
    QFrame[sidebar="true"] QPushButton {{
        background: transparent; color: {palette.sidebar_text};
        border: {px(1)}px solid transparent; text-align: left;
        min-height: {px(30)}px;
        padding: {px(6)}px {px(12)}px;
        border-radius: {px(10)}px;
        font-size: {fpx("nav")}px;
    }}
    QFrame[sidebar="true"] QPushButton:hover {{
        background: {palette.sidebar_hover}; border-color: {palette.sidebar_hover};
    }}
    QFrame[sidebar="true"] QPushButton:focus {{
        border: {px(2)}px solid {accent};
    }}
    QFrame[sidebar="true"] QPushButton[active="true"] {{
        background: {palette.sidebar_active}; color: {palette.sidebar_active_text};
        border-color: {palette.sidebar_active}; font-weight: {WEIGHT_MEDIUM};
    }}
    QFrame#userCard {{
        background: {palette.sidebar_hover};
        border: {px(1)}px solid {palette.sidebar_border};
        border-radius: {px(12)}px;
    }}
    QLabel#userAvatar {{
        background: {palette.sidebar_active}; color: {palette.sidebar_active_text};
        border: {px(1)}px solid {palette.sidebar_border};
        border-radius: {px(16)}px; font-weight: {WEIGHT_MEDIUM};
    }}
    QLabel#userName {{ font-weight: {WEIGHT_MEDIUM}; color: {palette.sidebar_text}; }}
    QFrame[sidebar="true"] QLabel#userRole {{
        color: {palette.sidebar_muted}; font-size: {fpx("small")}px;
    }}
    QFrame[sidebar="true"] QScrollBar:vertical {{
        background: transparent; width: {px(6)}px; margin: 0;
    }}
    QFrame[sidebar="true"] QScrollBar::handle:vertical {{
        background: {palette.sidebar_active}; border: none;
        border-radius: {px(3)}px; min-height: {px(24)}px;
    }}
    QFrame[sidebar="true"] QScrollBar::handle:vertical:hover {{
        background: {palette.sidebar_muted};
    }}
    QPushButton {{
        background: {palette.card};
        color: {palette.text};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(10)}px;
        padding: {px(9)}px {px(16)}px;
        min-height: {px(20)}px;
    }}
    QPushButton:hover {{ border-color: {palette.primary}; background: {palette.tint}; }}
    QPushButton:pressed {{ background: {palette.pressed}; color: #FFFFFF; }}
    QPushButton:focus {{ border: {px(2)}px solid {palette.primary}; }}
    QPushButton:disabled {{ color: {palette.muted}; background: {palette.input_fill}; }}
    QPushButton:checked {{ background: {palette.tint}; color: {palette.primary_text or palette.primary}; border-color: {palette.primary}; }}
    QPushButton[active="true"] {{
        background: {palette.card}; color: {palette.on_primary};
        border-color: {palette.card}; font-weight: {WEIGHT_MEDIUM};
    }}
    QPushButton[primary="true"] {{
        background: {palette.primary}; color: {palette.on_primary};
        border-color: {palette.primary}; font-weight: {WEIGHT_SEMIBOLD};
    }}
    QPushButton[primary="true"]:hover {{ background: {palette.hover}; }}
    QPushButton[primary="true"]:pressed {{ background: {palette.pressed}; color: #FFFFFF; }}
    QPushButton[primary="true"]:disabled {{
        background: {palette.tint}; color: {palette.muted}; border-color: {palette.border};
    }}
    QPushButton[checkout="true"] {{
        background: {palette.checkout}; color: {checkout_text};
        border-color: {palette.checkout}; font-weight: {WEIGHT_MEDIUM};
        border-radius: {px(12)}px; padding: {px(12)}px {px(16)}px;
        font-size: {fpx("section")}px;
    }}
    QPushButton[checkout="true"]:hover {{
        background: {checkout_hover}; border-color: {checkout_hover}; color: {checkout_text};
    }}
    QPushButton[checkout="true"]:pressed {{
        background: {checkout_pressed}; border-color: {checkout_pressed}; color: #FFFFFF;
    }}
    QPushButton[checkout="true"]:disabled {{
        background: {palette.surface_alt}; border-color: {palette.border}; color: {palette.muted};
    }}
    QPushButton[danger="true"] {{
        background: {palette.danger}; color: #FFFFFF;
        border-color: {palette.danger}; font-weight: {WEIGHT_SEMIBOLD};
    }}
    QPushButton[danger="true"]:hover {{ background: {danger_hover}; border-color: {danger_hover}; }}
    QPushButton[categoryChip="true"] {{
        background: {palette.surface_alt}; border-color: transparent; color: {palette.secondary};
        border-radius: {px(999)}px; padding: {px(7)}px {px(15)}px;
        font-weight: {WEIGHT_MEDIUM};
    }}
    QPushButton[categoryChip="true"]:hover {{
        background: {palette.tint}; color: {palette.primary_text or palette.primary};
        border-color: {palette.border};
    }}
    QPushButton[categoryChip="true"]:checked {{
        background: {palette.primary}; color: {palette.on_primary};
        border-color: {palette.primary};
    }}
    QToolButton {{
        background: {palette.card}; color: {palette.text};
        border: {px(1)}px solid {palette.border}; border-radius: {px(8)}px;
        padding: {px(5)}px;
    }}
    QToolButton:hover {{ border-color: {palette.primary}; background: {palette.tint}; }}
    QToolButton:pressed {{ background: {palette.pressed}; color: #FFFFFF; }}
    QToolButton:focus {{ border: {px(2)}px solid {palette.primary}; }}
    QToolButton:disabled {{ color: {palette.muted}; background: {palette.input_fill}; }}
    QToolButton[primary="true"] {{
        background: {palette.primary}; color: {palette.on_primary};
        border-color: {palette.primary};
    }}
    QToolButton[primary="true"]:hover {{ background: {palette.hover}; }}
    QToolButton[primary="true"]:pressed {{
        background: {palette.pressed}; color: #FFFFFF;
    }}
    QToolButton[primary="true"]:disabled {{
        background: {palette.input_fill}; color: {palette.muted};
        border-color: {palette.border};
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {palette.input_fill};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(10)}px;
        padding: {px(8)}px {px(10)}px;
        min-height: {px(22)}px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: {px(2)}px solid {palette.primary};
    }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
        color: {palette.muted}; background: {palette.canvas};
    }}
    QComboBox QAbstractItemView {{
        background: {palette.card}; color: {palette.text};
        selection-background-color: {palette.tint};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(10)}px; outline: 0; padding: {px(4)}px;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding; subcontrol-position: top right;
        width: {px(34)}px; border: none;
        border-left: {px(1)}px solid {palette.border};
        border-top-right-radius: {px(10)}px;
        border-bottom-right-radius: {px(10)}px;
    }}
    QComboBox::down-arrow {{
        image: url("{chevron_path}"); width: {px(13)}px; height: {px(13)}px;
    }}
    QComboBox QAbstractItemView::item {{
        min-height: {px(32)}px; padding: {px(6)}px {px(9)}px;
        border-radius: {px(6)}px;
    }}
    QCheckBox {{ spacing: {px(8)}px; }}
    QCheckBox::indicator {{
        width: {px(18)}px; height: {px(18)}px;
        border: {px(1)}px solid {palette.muted}; border-radius: {px(4)}px;
        background: {palette.card};
    }}
    QCheckBox::indicator:checked {{
        background: {palette.primary}; border-color: {palette.primary};
    }}
    QCheckBox:focus {{ outline: {px(2)}px solid {palette.primary}; }}
    QTableWidget {{
        background: {palette.card};
        alternate-background-color: {palette.card};
        border: {px(1)}px solid {palette.border};
        border-radius: {px(14)}px;
        gridline-color: transparent;
        selection-background-color: {palette.tint};
        selection-color: {palette.text};
        outline: 0;
    }}
    QTableWidget::item {{
        min-height: {px(38)}px;
        padding: {px(8)}px {px(10)}px;
        border-bottom: {px(1)}px solid {palette.hairline};
    }}
    QTableWidget::item:hover {{ background: {palette.canvas}; }}
    QHeaderView::section {{
        background: {palette.card};
        color: {palette.secondary};
        border: none;
        border-bottom: {px(1)}px solid {palette.border};
        padding: {px(12)}px {px(12)}px;
        font-weight: {WEIGHT_MEDIUM};
        font-size: {fpx("small")}px;
    }}
    QTableCornerButton::section {{
        background: {palette.card}; border: none;
        border-bottom: {px(1)}px solid {palette.border};
    }}
    QScrollBar:vertical {{
        background: transparent; width: {px(10)}px; margin: {px(4)}px {px(2)}px;
    }}
    QScrollBar::handle:vertical {{
        background: {palette.scrollbar}; min-height: {px(34)}px;
        border-radius: {px(5)}px; border: {px(2)}px solid {palette.canvas};
    }}
    QScrollBar::handle:vertical:hover {{ background: {palette.muted}; }}
    QScrollBar:horizontal {{
        background: transparent; height: {px(10)}px; margin: {px(2)}px {px(4)}px;
    }}
    QScrollBar::handle:horizontal {{
        background: {palette.scrollbar}; min-width: {px(34)}px;
        border-radius: {px(5)}px; border: {px(2)}px solid {palette.canvas};
    }}
    QScrollBar::handle:horizontal:hover {{ background: {palette.muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        height: {px(0)}px; background: transparent;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        width: {px(0)}px; background: transparent;
    }}
    QMenu {{
        background: {palette.card}; color: {palette.text};
        border: {px(1)}px solid {palette.border}; border-radius: {px(10)}px;
        padding: {px(5)}px;
    }}
    QMenu::item {{ padding: {px(8)}px {px(22)}px; border-radius: {px(6)}px; }}
    QMenu::item:selected {{
        background: {palette.tint}; color: {palette.primary_text or palette.primary};
    }}
    QToolTip {{
        color: {palette.text}; background: {palette.card};
        border: {px(1)}px solid {palette.border}; padding: {px(5)}px;
    }}
    QLabel#kpiLabel {{
        color: {palette.secondary}; font-size: {fpx("label")}px; font-weight: {WEIGHT_MEDIUM};
    }}
    QLabel#kpiValue {{ font-size: {fpx("kpi")}px; font-weight: {WEIGHT_MEDIUM}; }}
    QLabel#kpiDelta {{ color: {palette.success}; font-size: {fpx("small")}px; }}
    QLabel#productName, QLabel#drawerTitle {{ font-size: {fpx("body")}px; font-weight: {WEIGHT_MEDIUM}; }}
    QLabel#ticketCount {{ color: {palette.secondary}; font-size: {fpx("small")}px; }}
    QLabel#totalLabel {{ color: {palette.secondary}; }}
    QLabel#totalValue {{ font-weight: {WEIGHT_MEDIUM}; }}
    QLabel#grandLabel {{ font-size: {fpx("section")}px; font-weight: {WEIGHT_MEDIUM}; }}
    QLabel#grandValue {{ font-size: {fpx("total")}px; font-weight: {WEIGHT_STRONG}; }}
    QFrame#totalsDivider {{
        background: transparent; border: none;
        border-top: {px(1)}px dashed {palette.border};
        min-height: {px(1)}px; max-height: {px(1)}px;
    }}
    QFrame[cartLine="true"] {{
        background: transparent; border: none; border-radius: 0;
        border-bottom: {px(1)}px solid {palette.hairline};
    }}
    QLabel#cartEmpty {{ color: {palette.muted}; }}
    QLabel#cartItemName {{ font-weight: {WEIGHT_MEDIUM}; }}
    QLabel#productThumbnail {{
        background: {palette.tint}; color: {palette.primary_text or palette.primary};
        border-radius: {px(10)}px; font-size: {fpx("thumbnail")}px; font-weight: {WEIGHT_MEDIUM};
    }}
    QLabel#productPrice {{ font-size: {fpx("price")}px; font-weight: {WEIGHT_SEMIBOLD}; color: {palette.text}; }}
    QLabel#cartLineTotal, QLabel#receiptTotal {{
        font-weight: {WEIGHT_MEDIUM}; color: {palette.text};
    }}
    QLabel#stockStatus {{ color: {palette.secondary}; font-size: {fpx("small")}px; }}
    QLabel#stockStatus[stock="ok"] {{ color: {palette.success}; }}
    QLabel#stockStatus[stock="low"] {{ color: {palette.warning}; }}
    QLabel#stockStatus[stock="out"] {{ color: {palette.danger}; }}
    QLabel#statusPill {{
        background: {palette.success_tint}; color: {palette.success};
        border-radius: {px(999)}px; padding: {px(4)}px {px(10)}px;
        font-weight: {WEIGHT_MEDIUM};
    }}
    QLabel#statusPill[status="low"], QLabel#statusPill[status="pending"] {{
        background: {palette.warning_tint}; color: {palette.warning};
        border: {px(1)}px solid {palette.warning_accent};
    }}
    QLabel#statusPill[status="out"], QLabel#statusPill[status="failed"] {{
        background: {palette.danger_tint}; color: {palette.danger};
    }}
    QLabel#toast {{
        background: {palette.text}; color: {palette.card};
        border-radius: {px(10)}px; padding: {px(11)}px {px(16)}px;
    }}
    QFrame#receiptSeparator {{ border-top: {px(1)}px dashed {palette.border}; }}
    QLabel#receiptBusiness {{ font-size: {fpx("receipt_heading")}px; font-weight: {WEIGHT_SEMIBOLD}; }}
    QLabel#errorMessage {{ color: {palette.danger}; font-size: {fpx("error")}px; }}
    QProgressBar#receiptProgress {{
        background: {palette.border}; border: none; border-radius: {px(3)}px;
        max-height: {px(6)}px; text-align: center;
    }}
    QProgressBar#receiptProgress::chunk {{
        background: {palette.checkout}; border-radius: {px(3)}px;
    }}
    """
