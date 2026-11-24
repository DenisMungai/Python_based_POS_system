"""Central font configuration for the desktop UI.

This is the ONLY file you need to edit to change the app's typography.
No font files are downloaded or bundled: the names below refer to fonts that
are already installed on the computer.

IMPORTANT: Font settings are read once when the app starts. After saving a
change here, you MUST fully close the application (click X / Alt+F4) and run
`python main.py` again. Just looking at the old window will not show changes.

How to change the typeface
--------------------------
1. Change FONT_FAMILY to the name of any font installed on your system, e.g.
   "Arial", "Calibri", "Tahoma", "Segoe UI", "Verdana", "DejaVu Sans".
2. If that font is missing, the first available FONT_FALLBACKS entry is used
   and a warning is logged, so the app never fails to start.
3. Adjust FONT_SIZES if the new font reads larger or smaller than expected.

FONT_SIZES are literal screen pixels: the number you type is the size you get.
They still go through ``px()``, but with scaling and DPI compensation disabled
for fonts only (see gui/styles/tokens.py).

Receipt printing uses a monospace face so columns stay aligned on thermal
paper. It is configured separately below and does not affect the main UI.
"""

import logging
from collections.abc import Sequence

from gui.styles.tokens import px

LOGGER = logging.getLogger(__name__)

# --- Family selection -------------------------------------------------------

# Main UI family. Change this one line to restyle the whole application.
# These families are installed on a standard Windows system; no files needed.
FONT_FAMILIES = (
    "Calibri",
    "Segoe UI",
    "Arial",
    "Tahoma",
    "Verdana",
)
FONT_FAMILY = "Verdana"

# Used only when FONT_FAMILY is not installed on the current computer.
FONT_FALLBACKS = FONT_FAMILIES

# Monospace family used for printed / PDF thermal receipts.
RECEIPT_FONT_FAMILY = "Courier New"
RECEIPT_FONT_FALLBACKS = (
    "Courier New",
    "Consolas",
    "Lucida Console",
    "DejaVu Sans Mono",
    "Monospace",
)

# --- Named sizes (design pixels) -------------------------------------------

FONT_SIZES = {
    "body": 13,             # default text everywhere (matches .text-body ≈ .875rem at 90% base)
    "small": 11,            # hints, deltas, table headers, stock status (matches .text-small ≈ .75rem)
    "caption": 9,           # chart axis labels (matches .text-micro ≈ .625rem)
    "nav": 11,              # sidebar buttons (matches .75rem buttons)
    "sidebar_brand": 15,    # business name in the sidebar (matches market-page-title)
    "brand": 16,            # login brand name (matches .text-title ≈ 1.125rem)
    "callout": 16,          # welcome title, brand mark, login mark (matches .text-title ≈ 1.125rem)
    "section": 16,          # card section headings (matches .text-title ≈ 1.125rem)
    "kpi": 18,              # dashboard KPI figures (prominent but reduced)
    "thumbnail": 18,        # product placeholder letter
    "receipt_heading": 16,  # on-screen receipt business name
    "receipt": 9,           # printed / PDF receipt text (matches .text-micro ≈ .625rem)
    "error": 11,            # inline validation messages (matches .text-small ≈ .75rem)
}

# --- Weights ----------------------------------------------------------------

WEIGHT_MEDIUM = 600
WEIGHT_SEMIBOLD = 700

_warned_families: set[str] = set()


def fpx(token: str) -> int:
    """Return the scaled pixel size for a named entry in FONT_SIZES."""
    try:
        value = FONT_SIZES[token]
    except KeyError as error:
        raise KeyError(f"Unknown font size token: {token}") from error
    return px(value, scale=1.0, compensate_dpi=False)


def _installed_families() -> dict[str, str]:
    """Map lowercase family names to their installed spelling."""
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        return {}
    return {name.casefold(): name for name in QFontDatabase.families()}


def resolve_font_family(preferred: str, fallbacks: Sequence[str] = ()) -> str:
    """Return an installed family, preferring ``preferred`` then fallbacks."""
    installed = _installed_families()
    if not installed:
        return preferred  # Qt not initialised yet; nothing to verify against.

    exact = installed.get(preferred.casefold())
    if exact is not None:
        return exact

    for candidate in fallbacks:
        exact = installed.get(candidate.casefold())
        if exact is not None:
            key = preferred.casefold()
            if key not in _warned_families:
                LOGGER.warning(
                    "Font '%s' is not installed on this computer; using '%s'. "
                    "Change FONT_FAMILY in gui/styles/fonts.py to choose another.",
                    preferred, exact,
                )
                _warned_families.add(key)
            return exact

    sample = ", ".join(sorted(installed.values())[:10])
    raise RuntimeError(
        f"Font '{preferred}' is not installed and no fallback was found. "
        f"Installed fonts include: {sample}"
    )


def ui_font_family() -> str:
    """Return the installed family to use for the main interface."""
    return resolve_font_family(FONT_FAMILY, FONT_FALLBACKS)


def receipt_font_family() -> str:
    """Return the installed monospace family to use for printed receipts."""
    return resolve_font_family(RECEIPT_FONT_FAMILY, RECEIPT_FONT_FALLBACKS)


__all__ = [
    "FONT_FALLBACKS", "FONT_FAMILIES", "FONT_FAMILY", "FONT_SIZES", "RECEIPT_FONT_FALLBACKS",
    "RECEIPT_FONT_FAMILY", "WEIGHT_MEDIUM", "WEIGHT_SEMIBOLD",
    "fpx", "receipt_font_family", "resolve_font_family", "ui_font_family",
]
