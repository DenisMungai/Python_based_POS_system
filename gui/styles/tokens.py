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
    # Premium chrome: a dark navigation rail shared by every palette, with a
    # brighter accent that stays legible on it. ``None`` falls back to primary.
    sidebar: str = "#13171C"
    sidebar_hover: str = "#1C2128"
    sidebar_active: str = "#242B34"
    sidebar_text: str = "#E6E9EE"
    sidebar_active_text: str = "#FFFFFF"
    checkout_text: str | None = None
    sidebar_muted: str = "#8B94A1"
    sidebar_border: str = "#242B34"
    accent_on_dark: str | None = None
    surface_alt: str = "#F1F5F9"
    hairline: str = "#EEF2F6"
    success_tint: str = "#E7F6EC"

    @property
    def accent(self) -> str:
        """Accent colour for use on the dark navigation rail."""
        return self.accent_on_dark or self.primary


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

# Warm, restaurant-grade surfaces for the optional Obsidian palette.
_WARM = {
    **_BASE,
    "canvas": "#F7F4EE", "border": "#E8E2D4", "input_fill": "#FBF9F4",
    "text": "#1B1D22", "secondary": "#6B6F78", "muted": "#9A9DA5",
    "scrollbar": "#D8D1C0",
}

PALETTES: dict[str, Palette] = {
    "Navy": Palette(
        "Navy", "#1D4ED8", "#1E40AF", "#1E3A8A", "#EFF6FF", "#FFFFFF",
        accent_on_dark="#6B9BFF", **_BASE,
        sidebar="#101C3D", sidebar_hover="#182750", sidebar_active="#E8EEFB",
        sidebar_text="#E7ECF9", sidebar_muted="#93A3C7", sidebar_border="#22315A",
        sidebar_active_text="#1E3A8A",
    ),
    # Deep evergreen surfaces with restrained champagne-brass actions create a
    # quieter, hospitality-grade default without hard-coding a business brand.
    "Emerald": Palette(
        "Emerald", "#A7864F", "#927342", "#765B32", "#F3EEE4", "#FFFFFF",
        primary_text="#70572F", accent_on_dark="#C9A96A", checkout_text="#FFFFFF",
        **{
            **_BASE,
            "canvas": "#F4F2ED", "border": "#E6E0D5", "input_fill": "#FAF9F6",
            "text": "#252A27", "secondary": "#72776F", "muted": "#A3A49C",
            "success": "#287653", "danger": "#B64B45", "warning": "#9B7138",
            "scrollbar": "#D3CEC3", "danger_tint": "#F9EEEC",
            "warning_tint": "#F7F0E4", "checkout": "#267456",
            "warning_accent": "#A7864F",
        },
        surface_alt="#F0ECE3", hairline="#EEE9DF", success_tint="#E7F1EB",
        sidebar="#172D2A", sidebar_hover="#20403B", sidebar_active="#EAE3D6",
        sidebar_text="#F4F1E9", sidebar_muted="#9DB0AA", sidebar_border="#28443F",
        sidebar_active_text="#263A34",
    ),
    "Teal": Palette(
        "Teal", "#0F766E", "#115E59", "#134E4A", "#F0FDFA", "#FFFFFF",
        accent_on_dark="#2DD4BF", **_BASE,
        sidebar="#0B2E2B", sidebar_hover="#113E39", sidebar_active="#DCF3EE",
        sidebar_text="#E4F3F0", sidebar_muted="#8CB3AD", sidebar_border="#17433E",
        sidebar_active_text="#0B4A45",
    ),
    "Amber": Palette(
        "Amber", "#B45309", "#92400E", "#78350F", "#FFFBEB", "#FFFFFF",
        accent_on_dark="#FBBF24", **_BASE,
        sidebar="#2E1F10", sidebar_hover="#3E2B16", sidebar_active="#F7E8CD",
        sidebar_text="#F7EFE2", sidebar_muted="#BCA98B", sidebar_border="#46331C",
        sidebar_active_text="#7A4A0B",
    ),
    "Red": Palette(
        "Red", "#DC2626", "#B91C1C", "#991B1B", "#FEF2F2", "#FFFFFF",
        accent_on_dark="#F87171", **_BASE,
        sidebar="#3A1515", sidebar_hover="#4C1C1C", sidebar_active="#FAE5E3",
        sidebar_text="#FAEDEC", sidebar_muted="#C6A09D", sidebar_border="#552120",
        sidebar_active_text="#8E1F1F",
    ),
    "Slate": Palette(
        "Slate", "#1E293B", "#334155", "#0F172A", "#F1F5F9", "#FFFFFF",
        accent_on_dark="#94A3B8", **_BASE,
        sidebar="#0E1626", sidebar_hover="#172136", sidebar_active="#E3E9F2",
        sidebar_text="#E8EDF5", sidebar_muted="#94A3B8", sidebar_border="#1E2B42",
        sidebar_active_text="#1E293B",
    ),
    "Obsidian": Palette(
        "Obsidian", "#16181D", "#2A2E36", "#0B0C0F", "#F4EFE3", "#F7F3EA",
        primary_text="#7A5C1E", accent_on_dark="#D4AF6A",
        surface_alt="#F1ECE0", hairline="#EFEADD", success_tint="#E8F3EA",
        sidebar="#111317", sidebar_hover="#1B1E24", sidebar_active="#2A2620",
        sidebar_text="#F3EFE6", sidebar_muted="#A69E8E", sidebar_border="#26231D",
        sidebar_active_text="#F1E5CE",
        **{**_WARM, "checkout": "#B8924A"},
    ),
}

DEFAULT_PALETTE = PALETTES["Emerald"]

_active_palette: Palette | None = None


def set_active_palette(palette: Palette) -> None:
    """Record the palette in use so widgets built later pick up its colours."""
    global _active_palette
    _active_palette = palette


def active_palette() -> Palette:
    """Return the palette selected for this session, or the default."""
    return _active_palette or DEFAULT_PALETTE

__all__ = [
    "DEFAULT_PALETTE", "PALETTES", "Palette", "UI_SCALE", "active_palette",
    "configure_ui_scale", "px", "set_active_palette",
]
