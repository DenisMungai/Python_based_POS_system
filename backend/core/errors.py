"""Typed, user-safe errors raised by backend operations."""


class PosError(Exception):
    """Base error for expected point-of-sale failures."""

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationError(PosError):
    """Raised when supplied business data is invalid."""


class NotFoundError(PosError):
    """Raised when a requested record does not exist."""


class DuplicateError(PosError):
    """Raised when a unique business value already exists."""


class InsufficientStockError(PosError):
    """Raised when a sale requests more stock than is available."""


class PermissionDeniedError(PosError):
    """Raised when the current user lacks a required permission."""


class AuthenticationError(PosError):
    """Raised when credentials are invalid."""


class AccountLockedError(AuthenticationError):
    """Raised when login is temporarily locked after repeated failures."""


class VoucherError(ValidationError):
    """Raised when a voucher cannot be applied."""


class PaymentError(ValidationError):
    """Raised when payment data does not cover or conform to a sale."""


class ImportErrorReport(ValidationError):
    """Raised when CSV import contains row-level validation errors."""

    def __init__(self, errors: list[dict[str, object]]) -> None:
        super().__init__("The import contains invalid rows.", errors=errors)
        self.errors = errors


class DatabaseError(PosError):
    """Raised when repository persistence fails."""


class MigrationError(DatabaseError):
    """Raised when a database migration fails."""
