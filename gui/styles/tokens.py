"""Scaled design tokens and curated palettes based on the supplied POS colors."""

from dataclasses import dataclass
from math import isfinite

UI_SCALE = 0.9
_DPI_SCALE = 1.0


def px(
    value: int | float,
    *,
    scale: float | None = None,
    compensate_dpi: bool = True,
) -> int:
    """Scale design pixels for the configured root zoom and display DPI.

    Font sizes pass ``scale=1.0`` and ``compensate_dpi=False`` so the numbers
    in FONT_SIZES are literal screen pixels. Every other UI value keeps the
    shared UI_SCALE and high-DPI compensation.
    """
    factor = UI_SCALE if scale is None else scale
    dpi = _DPI_SCALE if compensate_dpi else 1.0
    scaled = value * factor * dpi
    result = round(scaled)
    return max(1, result) if value > 0 else result


def configure_ui_scale(device_pixel_ratio: float) -> None:
    """Compensate Qt logical pixel dimensions for the primary display's DPR."""
    global _DPI_SCALE
    if not isfinite(device_pixel_ratio) or device_pixel_ratio <= 0:
        raise ValueError("Display device-pixel ratio must be a positive finite number.")
    _DPI_SCALE = 1 / max(device_pixel_ratio, 1.0)


@dataclass(frozen=True)
class Palette:
    """Shared surface, text, feedback, and accent colors."""

    name: str
    primary: str
    hover: str
    pressed: str
    tint: str
    on_primary: str
    primary_text: str | None = None
    canvas: str = "#F8FAFC"
    card: str = "#FFFFFF"
    border: str = "#E2E8F0"
    input_fill: str = "#F8FAFC"
    text: str = "#1E293B"
    secondary: str = "#64748B"
    muted: str = "#94A3B8"
    success: str = "#16A34A"
    danger: str = "#DC2626"
    warning: str = "#D97706"
    scrollbar: str = "#CBD5E1"
    danger_tint: str = "#FEF2F2"
    warning_tint: str = "#FFFBEB"
    checkout: str = "#15A046"
    warning_accent: str = "#D97706"


_BASE = {
    "canvas": "#F8FAFC",
    "card": "#FFFFFF",
    "border": "#E2E8F0",
    "input_fill": "#F8FAFC",
    "text": "#1E293B",
    "secondary": "#64748B",
    "muted": "#94A3B8",
    "success": "#15803D",
    "danger": "#DC2626",
    "warning": "#B45309",
    "scrollbar": "#CBD5E1",
    "danger_tint": "#FEF2F2",
    "warning_tint": "#FFFBEB",
    "checkout": "#15A046",
    "warning_accent": "#D97706",
}

PALETTES: dict[str, Palette] = {
    "Navy": Palette("Navy", "#1D4ED8", "#1E40AF", "#1E3A8A", "#EFF6FF", "#FFFFFF", **_BASE),
    "Emerald": Palette(
        "Emerald", "#15A046", "#19A84B", "#0F7032", "#E9F7EE", "#071A0D",
        primary_text="#116B35", **_BASE,
    ),
    "Teal": Palette("Teal", "#0F766E", "#115E59", "#134E4A", "#F0FDFA", "#FFFFFF", **_BASE),
    "Amber": Palette("Amber", "#B45309", "#92400E", "#78350F", "#FFFBEB", "#FFFFFF", **_BASE),
    "Red": Palette("Red", "#DC2626", "#B91C1C", "#991B1B", "#FEF2F2", "#FFFFFF", **_BASE),
    "Slate": Palette("Slate", "#1E293B", "#334155", "#0F172A", "#F1F5F9", "#FFFFFF", **_BASE),
}

DEFAULT_PALETTE = PALETTES["Emerald"]

__all__ = [
    "DEFAULT_PALETTE", "PALETTES", "Palette", "UI_SCALE",
    "configure_ui_scale", "px",
]
