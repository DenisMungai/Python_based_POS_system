"""In-memory cart intent; service checkout re-reads prices and stock."""

from dataclasses import dataclass

from backend.core.errors import ValidationError


@dataclass(frozen=True)
class CartLine:
    """A requested item and quantity, without a client-authoritative price."""

    item_id: int
    quantity_milli: int


class Cart:
    """Collect sale item IDs and quantities before service validation."""

    def __init__(self) -> None:
        self._quantities: dict[int, int] = {}

    def add(self, item_id: int, quantity_milli: int = 1000) -> None:
        """Add a positive quantity to a cart line."""
        if item_id <= 0 or quantity_milli <= 0:
            raise ValidationError("Cart item and quantity must be positive.")
        self._quantities[item_id] = self._quantities.get(item_id, 0) + quantity_milli

    def set_quantity(self, item_id: int, quantity_milli: int) -> None:
        """Set a line quantity, removing the line when quantity is zero."""
        if item_id not in self._quantities:
            raise ValidationError("Cart item was not found.")
        if quantity_milli < 0:
            raise ValidationError("Cart quantity cannot be negative.")
        if quantity_milli == 0:
            self.remove(item_id)
        else:
            self._quantities[item_id] = quantity_milli

    def remove(self, item_id: int) -> None:
        """Remove an item line when present."""
        self._quantities.pop(item_id, None)

    def clear(self) -> None:
        """Remove all lines."""
        self._quantities.clear()

    def lines(self) -> tuple[CartLine, ...]:
        """Return a stable snapshot of current cart intent."""
        return tuple(CartLine(item_id, quantity) for item_id, quantity in self._quantities.items())

    def to_sale_lines(self) -> list[dict[str, int]]:
        """Return the input shape accepted by `SalesService.process_sale`."""
        return [{"item_id": line.item_id, "quantity_milli": line.quantity_milli}
                for line in self.lines()]

    def __len__(self) -> int:
        """Return the number of distinct item lines."""
        return len(self._quantities)
