"""Typed records used by backend services and GUI consumers."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UserContext:
    """Authenticated user identity and role."""

    id: int
    username: str
    display_name: str
    role: str
    must_change_password: bool = False


@dataclass(frozen=True)
class SaleResult:
    """Persisted sale summary returned after a successful transaction."""

    id: int
    receipt_number: str
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    change_minor: int
    items: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ImportPreview:
    """Dry-run import result with valid rows and row-specific errors."""

    rows: tuple[dict[str, str], ...]
    errors: tuple[dict[str, object], ...]
