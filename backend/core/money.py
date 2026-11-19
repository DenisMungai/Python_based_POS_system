"""Exact money, quantity, and tax conversions using integer storage."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from backend.core.errors import ValidationError


def _decimal(value: str | int | Decimal) -> Decimal:
    if isinstance(value, bool):
        raise ValidationError("A numeric value is required.")
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("A valid numeric value is required.") from error
    if not result.is_finite():
        raise ValidationError("The value must be finite.")
    return result


def to_minor(amount: str | int | Decimal, decimals: int = 2) -> int:
    """Convert a major-unit amount to integer minor units."""
    if decimals < 0:
        raise ValidationError("Currency decimals cannot be negative.")
    return int((_decimal(amount) * (10**decimals)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_minor(amount: int, decimals: int = 2) -> Decimal:
    """Convert integer minor units to a Decimal major-unit amount."""
    if isinstance(amount, bool) or not isinstance(amount, int) or decimals < 0:
        raise ValidationError("Minor units and currency decimals must be integers.")
    return Decimal(amount).scaleb(-decimals)


def fmt(amount_minor: int, currency: str = "KES", decimals: int = 2) -> str:
    """Format integer minor units for display."""
    amount = from_minor(amount_minor, decimals)
    return f"{currency} {amount:,.{decimals}f}"


def apply_tax(amount_minor: int, rate_basis_points: int) -> int:
    """Return rounded tax for an exclusive-tax amount."""
    if rate_basis_points < 0:
        raise ValidationError("Tax rate cannot be negative.")
    return int(
        (Decimal(amount_minor) * Decimal(rate_basis_points) / Decimal(10_000))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def extract_inclusive_tax(amount_minor: int, rate_basis_points: int) -> int:
    """Extract the tax portion from a tax-inclusive amount."""
    if rate_basis_points < 0:
        raise ValidationError("Tax rate cannot be negative.")
    if rate_basis_points == 0:
        return 0
    return int(
        (Decimal(amount_minor) * Decimal(rate_basis_points) / Decimal(10_000 + rate_basis_points))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def qty_to_milli(quantity: str | int | Decimal) -> int:
    """Convert a quantity to integer thousandths."""
    value = _decimal(quantity)
    milli = value * 1000
    if milli != milli.to_integral_value():
        raise ValidationError("Quantity supports at most three decimal places.")
    return int(milli)


def milli_to_qty(quantity_milli: int) -> Decimal:
    """Convert integer thousandths to a Decimal quantity."""
    if isinstance(quantity_milli, bool) or not isinstance(quantity_milli, int):
        raise ValidationError("Quantity milli-units must be an integer.")
    return Decimal(quantity_milli).scaleb(-3)
