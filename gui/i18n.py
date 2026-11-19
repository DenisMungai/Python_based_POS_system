"""Business-configurable terminology lookup for visible interface labels."""

from backend.core.errors import NotFoundError
from backend.services.catalog import SettingsService

_settings: SettingsService | None = None


def configure_terminology(settings: SettingsService) -> None:
    """Set the settings service used by the module-level translation helper."""
    global _settings
    _settings = settings


def t(key: str, default: str | None = None) -> str:
    """Return configured terminology, with an explicit optional fallback."""
    if _settings is None:
        if default is not None:
            return default
        raise RuntimeError("Terminology service has not been configured.")
    try:
        return _settings.term(key)
    except NotFoundError:
        if default is not None:
            return default
        raise
