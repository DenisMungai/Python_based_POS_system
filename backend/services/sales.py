"""Atomic checkout, held-sale, returns, and sales-history services."""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from backend.core.errors import (
    InsufficientStockError, NotFoundError, PaymentError, ValidationError,
)
from backend.core.events import EventBus
from backend.core.money import apply_tax, extract_inclusive_tax, qty_to_milli
from backend.models.records import SaleResult
from backend.repositories.sqlite_repository import SqliteRepository
from backend.services.catalog import AuthService, DiscountService, timestamp, utc_now


def _line_amount(unit_price_minor: int, quantity_milli: int) -> int:
    """Multiply minor units by thousandths with half-up rounding."""
    return int((Decimal(unit_price_minor * quantity_milli) / Decimal(1000)).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))


class SalesService:
    """Process sales and ensure stock, payments, receipts, and totals commit together."""

    def __init__(self, repository: SqliteRepository, events: EventBus, auth: AuthService | None = None) -> None:
        self.repo, self.events = repository, events
        self.auth = auth
        self.discounts = DiscountService(repository, auth)

    def quote_sale(
        self, lines: list[dict[str, Any]], voucher_code: str | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        """Return server-calculated sale lines and totals without changing data."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.process")
        if not lines:
            raise ValidationError("A sale requires at least one item.")
        now = at or utc_now()
        prepared: list[dict[str, Any]] = []
        subtotal = tax_total = 0
        requirements: dict[int, int] = {}
        for line in lines:
            item_id = int(line["item_id"])
            item = self.repo.get("items", item_id)
            if not item or item["archived"]:
                raise NotFoundError("A sale item is no longer available.", item_id=item_id)
            quantity = int(line["quantity_milli"]) if "quantity_milli" in line else qty_to_milli(line.get("quantity", 1))
            if quantity <= 0:
                raise ValidationError("Sale quantities must be positive.")
            if item["item_type"] in {"product", "weighed"}:
                requirements[item_id] = requirements.get(item_id, 0) + quantity
            elif item["item_type"] == "bundle":
                for component in self.repo.find("item_components", {"item_id": item_id}):
                    needed = (int(component["quantity_milli"]) * quantity + 999) // 1000
                    requirements[component["component_id"]] = requirements.get(component["component_id"], 0) + needed
            rate = 0
            if item["tax_rate_id"] is not None:
                tax_row = self.repo.get("tax_rates", item["tax_rate_id"])
                if tax_row:
                    rate = int(tax_row["rate_basis_points"])
            gross = _line_amount(int(item["price_minor"]), quantity)
            tax = extract_inclusive_tax(gross, rate) if item["tax_inclusive"] else apply_tax(gross, rate)
            base = gross - tax if item["tax_inclusive"] else gross
            line_total = gross if item["tax_inclusive"] else gross + tax
            prepared.append({
                "item_id": item_id, "name": item["name"], "item_type": item["item_type"],
                "unit_price_minor": item["price_minor"], "quantity_milli": quantity,
                "tax_rate_basis_points": rate, "tax_inclusive": bool(item["tax_inclusive"]),
                "line_subtotal_minor": base, "line_tax_minor": tax, "line_total_minor": line_total,
            })
            subtotal += base
            tax_total += tax
        for item_id, quantity in requirements.items():
            item = self.repo.get("items", item_id)
            if not item or item["stock_milli"] < quantity:
                raise InsufficientStockError("There is not enough stock to complete this sale.", item_id=item_id)
        discount = 0
        if voucher_code:
            voucher = self.discounts.validate_voucher(voucher_code, subtotal, now)
            discount = int(voucher["discount_minor"])
            remaining = discount
            for index, line in enumerate(prepared):
                share = remaining if index == len(prepared) - 1 else (
                    discount * line["line_subtotal_minor"] // subtotal if subtotal else 0
                )
                share = min(share, line["line_subtotal_minor"], remaining)
                remaining -= share
                line["line_subtotal_minor"] -= share
                line["line_tax_minor"] = apply_tax(
                    line["line_subtotal_minor"], line["tax_rate_basis_points"]
                )
                line["line_total_minor"] = line["line_subtotal_minor"] + line["line_tax_minor"]
            subtotal = sum(line["line_subtotal_minor"] for line in prepared)
            tax_total = sum(line["line_tax_minor"] for line in prepared)
        return {
            "lines": prepared, "subtotal_minor": subtotal, "tax_minor": tax_total,
            "discount_minor": discount, "total_minor": subtotal + tax_total,
        }

    def process_sale(
        self,
        lines: list[dict[str, Any]],
        payments: list[dict[str, Any]],
        customer_id: int | None = None,
        voucher_code: str | None = None,
        note: str = "",
        user_id: int | None = None,
        at: datetime | None = None,
    ) -> SaleResult:
        """Validate and commit one complete sale in a single immediate transaction."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.process")
        if not lines or not payments:
            raise ValidationError("A sale requires at least one item and one payment.")
        now = at or utc_now()
        created_at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
        date_key = now.astimezone(timezone.utc).strftime("%Y%m%d")
        prepared: list[dict[str, Any]] = []
        subtotal = tax_total = 0
        with self.repo.database.transaction():
            if customer_id is not None and not self.repo.get("customers", customer_id):
                raise NotFoundError("Customer was not found.")
            stock_requirements: dict[int, int] = {}
            for line in lines:
                item_id = int(line["item_id"])
                item = self.repo.get("items", item_id)
                if not item or item["archived"]:
                    raise NotFoundError("A sale item is no longer available.", item_id=item_id)
                quantity = int(line["quantity_milli"]) if "quantity_milli" in line else qty_to_milli(line.get("quantity", 1))
                if quantity <= 0:
                    raise ValidationError("Sale quantities must be positive.")
                if item["item_type"] in {"product", "weighed"}:
                    stock_requirements[item_id] = stock_requirements.get(item_id, 0) + quantity
                elif item["item_type"] == "bundle":
                    for component in self.repo.find("item_components", {"item_id": item_id}):
                        needed = (int(component["quantity_milli"]) * quantity + 999) // 1000
                        stock_requirements[component["component_id"]] = stock_requirements.get(component["component_id"], 0) + needed
                rate = 0
                if item["tax_rate_id"] is not None:
                    tax_row = self.repo.get("tax_rates", item["tax_rate_id"])
                    if tax_row:
                        rate = int(tax_row["rate_basis_points"])
                gross = _line_amount(int(item["price_minor"]), quantity)
                inclusive = bool(item["tax_inclusive"])
                line_tax = extract_inclusive_tax(gross, rate) if inclusive else apply_tax(gross, rate)
                line_subtotal = gross - line_tax if inclusive else gross
                line_total = gross if inclusive else gross + line_tax
                subtotal += line_subtotal
                tax_total += line_tax
                prepared.append({
                    "item": item, "quantity_milli": quantity, "line_subtotal_minor": line_subtotal,
                    "line_tax_minor": line_tax, "line_total_minor": line_total,
                    "tax_rate_basis_points": rate,
                })
            for item_id, required in stock_requirements.items():
                item = self.repo.get("items", item_id)
                if not item or int(item["stock_milli"]) < required:
                    available = int(item["stock_milli"]) if item else 0
                    raise InsufficientStockError(
                        "There is not enough stock to complete this sale.",
                        item_id=item_id, requested_milli=required, available_milli=available,
                    )
            voucher = None
            discount = 0
            if voucher_code:
                undiscounted_subtotal = subtotal
                voucher = self.discounts.validate_voucher(voucher_code, undiscounted_subtotal, now)
                discount = int(voucher["discount_minor"])
                remaining_discount = discount
                for index, line in enumerate(prepared):
                    base = int(line["line_subtotal_minor"])
                    share = remaining_discount if index == len(prepared) - 1 else (
                        discount * base // undiscounted_subtotal if undiscounted_subtotal else 0
                    )
                    share = min(share, base, remaining_discount)
                    remaining_discount -= share
                    discounted_base = base - share
                    recalculated_tax = apply_tax(discounted_base, line["tax_rate_basis_points"])
                    line["line_subtotal_minor"] = discounted_base
                    line["line_tax_minor"] = recalculated_tax
                    line["line_total_minor"] = discounted_base + recalculated_tax
                subtotal = sum(int(line["line_subtotal_minor"]) for line in prepared)
                tax_total = sum(int(line["line_tax_minor"]) for line in prepared)
            total = subtotal + tax_total
            received = 0
            cash_received = 0
            for payment in payments:
                method = str(payment.get("method", "")).strip()
                amount = int(payment.get("amount_minor", 0))
                reference = str(payment.get("reference", "")).strip()
                if amount <= 0 or not method:
                    raise PaymentError("Payment methods and amounts must be valid.")
                enabled = self.repo.find("payment_methods", {"name": method, "active": 1}, limit=1)
                if not enabled:
                    raise PaymentError("This payment method is not enabled.", method=method)
                if method.casefold() in {"m-pesa", "mpesa"} and not reference:
                    raise PaymentError("An M-Pesa reference is required.")
                received += amount
                if method.casefold() == "cash":
                    cash_received += amount
            if received < total:
                raise PaymentError("Payment does not cover the sale total.", due_minor=total, paid_minor=received)
            change = received - total
            if change > cash_received:
                raise PaymentError("Change can only be given from cash tendered.")
            receipt_number = self.repo.next_number(date_key, "RCP")
            sale_id = self.repo.insert("sales", {
                "uuid": str(uuid.uuid4()), "receipt_number": receipt_number,
                "customer_id": customer_id, "status": "completed", "subtotal_minor": subtotal,
                "discount_minor": discount, "tax_minor": tax_total, "total_minor": total,
                "change_minor": change, "voucher_code": voucher["code"] if voucher else None,
                "note": note, "created_at": created_at, "created_by": user_id,
            })
            for line in prepared:
                item = line["item"]
                self.repo.insert("sale_items", {
                    "sale_id": sale_id, "item_id": item["id"], "name_snapshot": item["name"],
                    "item_type": item["item_type"], "unit_price_minor": item["price_minor"],
                    "cost_minor": item["cost_minor"], "tax_rate_basis_points": line["tax_rate_basis_points"],
                    "tax_inclusive": item["tax_inclusive"], "quantity_milli": line["quantity_milli"],
                    "line_subtotal_minor": line["line_subtotal_minor"], "line_tax_minor": line["line_tax_minor"],
                    "line_total_minor": line["line_total_minor"],
                })
            for payment in payments:
                self.repo.insert("sale_payments", {
                    "sale_id": sale_id, "method": payment["method"],
                    "amount_minor": int(payment["amount_minor"]),
                    "reference": str(payment.get("reference", "")),
                })
            low_stock_crossings: list[tuple[int, int]] = []
            changed_items: list[tuple[int, int]] = []
            for item_id, required in stock_requirements.items():
                item = self.repo.get("items", item_id)
                before = int(item["stock_milli"])
                if not self.repo.stock_update(item_id, -required, created_at):
                    raise InsufficientStockError("Stock changed during checkout.", item_id=item_id)
                self.repo.insert("stock_movements", {
                    "item_id": item_id, "quantity_delta_milli": -required, "reason": "sale",
                    "reference": receipt_number, "created_at": created_at, "created_by": user_id,
                })
                after = before - required
                changed_items.append((item_id, after))
                if item["low_stock_milli"] and before > item["low_stock_milli"] >= after:
                    low_stock_crossings.append((item_id, after))
            if voucher:
                self.repo.update("vouchers", voucher["id"], {"used_count": int(voucher["used_count"]) + 1})
            self.repo.insert("audit_log", {
                "user_id": user_id, "action": "sale_completed", "entity": "sales",
                "entity_id": str(sale_id), "details_json": json.dumps({"receipt": receipt_number}),
                "created_at": created_at,
            })
            self.repo.insert_outbox("sales", self.repo.get("sales", sale_id)["uuid"], "create",
                                    {"receipt_number": receipt_number}, created_at)
            saved_items = tuple(self.repo.find("sale_items", {"sale_id": sale_id}, order_by="id"))
        for item_id, stock in changed_items:
            self.events.publish("stock_changed", item_id=item_id, stock_milli=stock)
        for item_id, stock in low_stock_crossings:
            self.events.publish("low_stock_alert", item_id=item_id, stock_milli=stock)
        self.events.publish("sale_completed", sale_id=sale_id, receipt_number=receipt_number)
        return SaleResult(sale_id, receipt_number, subtotal, discount, tax_total, total, change, saved_items)

    def hold_sale(self, lines: list[dict[str, Any]], customer_id: int | None = None, note: str = "") -> int:
        """Save a cart for later recall without changing stock."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.process")
        if not lines:
            raise ValidationError("Cannot hold an empty sale.")
        return self.repo.insert("held_sales", {
            "uuid": str(uuid.uuid4()), "customer_id": customer_id,
            "cart_json": json.dumps(lines), "note": note, "created_at": timestamp(),
        })

    def recall_held(self, held_id: int, remove: bool = True) -> dict[str, Any]:
        """Retrieve a held cart and optionally remove its saved copy."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.process")
        held = self.repo.get("held_sales", held_id)
        if not held:
            raise NotFoundError("Held sale was not found.")
        result = {**held, "lines": json.loads(held["cart_json"])}
        if remove:
            self.repo.delete("held_sales", held_id)
        return result

    def list_held(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent saved carts with their decoded item requests."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.process")
        if not 1 <= limit <= 1000:
            raise ValidationError("Held-sale limit must be between 1 and 1000.")
        rows = self.repo.find("held_sales", order_by="created_at", descending=True, limit=limit)
        return [{**row, "lines": json.loads(row["cart_json"])} for row in rows]

    def get_sale(self, sale_id: int) -> dict[str, Any]:
        """Return a sale with immutable item snapshots and payment rows."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.read")
        sale = self.repo.get("sales", sale_id)
        if not sale:
            raise NotFoundError("Sale was not found.")
        return {**sale, "items": self.repo.find("sale_items", {"sale_id": sale_id}, order_by="id"),
                "payments": self.repo.find("sale_payments", {"sale_id": sale_id}, order_by="id")}

    def list_sales(self, limit: int = 100) -> list[dict[str, Any]]:
        """List recent sales."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.read")
        return self.repo.find("sales", order_by="created_at", descending=True, limit=limit)

    def void_sale(self, sale_id: int, reason: str, user_id: int | None = None) -> None:
        """Void a completed sale, restore stock, and record an audit entry."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.void")
        if not reason.strip():
            raise ValidationError("A void reason is required.")
        now = timestamp()
        changes: list[tuple[int, int]] = []
        with self.repo.database.transaction():
            sale = self.repo.get("sales", sale_id)
            if not sale or sale["status"] != "completed":
                raise ValidationError("Only completed sales can be voided.")
            movements = self.repo.find("stock_movements", {"reference": sale["receipt_number"]})
            for movement in movements:
                item_id = int(movement["item_id"])
                already_returned = self.repo.restocked_return_quantity(sale_id, item_id)
                inverse = -int(movement["quantity_delta_milli"]) - already_returned
                if inverse <= 0:
                    continue
                self.repo.stock_update(item_id, inverse, now)
                self.repo.insert("stock_movements", {
                    "item_id": item_id, "quantity_delta_milli": inverse, "reason": "sale_void",
                    "reference": sale["receipt_number"], "created_at": now, "created_by": user_id,
                })
                current = self.repo.get("items", item_id)
                changes.append((item_id, int(current["stock_milli"])))
            self.repo.update("sales", sale_id, {"status": "voided"})
            self.repo.insert("audit_log", {
                "user_id": user_id, "action": "sale_voided", "entity": "sales",
                "entity_id": str(sale_id), "details_json": json.dumps({"reason": reason}),
                "created_at": now,
            })
            self.repo.insert_outbox("sales", sale["uuid"], "update", {"status": "voided"}, now)
        for item_id, stock in changes:
            self.events.publish("stock_changed", item_id=item_id, stock_milli=stock)


class ReturnService:
    """Return sold lines and optionally restore their stock."""

    def __init__(self, repository: SqliteRepository, events: EventBus, auth: AuthService | None = None) -> None:
        self.repo, self.events, self.auth = repository, events, auth

    def find_sale_by_receipt(self, receipt_number: str) -> dict[str, Any]:
        """Find a sale and its receipt snapshots by exact receipt number."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.read")
        rows = self.repo.find("sales", {"receipt_number": receipt_number}, limit=1)
        if not rows:
            raise NotFoundError("Receipt was not found.")
        sale = rows[0]
        return {**sale, "items": self.repo.find("sale_items", {"sale_id": sale["id"]}, order_by="id")}

    def list_returns(self, limit: int = 100) -> list[dict[str, Any]]:
        """List recent returns with their original receipt numbers."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.read")
        returns = self.repo.find("returns", order_by="created_at", descending=True, limit=limit)
        result = []
        for return_row in returns:
            sale = self.repo.get("sales", int(return_row["sale_id"]))
            result.append({
                **return_row,
                "receipt_number": sale["receipt_number"] if sale else "",
            })
        return result

    def create_return(
        self, sale_id: int, items: list[dict[str, Any]], restock: bool = True,
        note: str = "", user_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a partial or full return and optionally restock returned items."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("sales.return")
        if not items:
            raise ValidationError("At least one sale line must be returned.")
        now = timestamp()
        changed: list[tuple[int, int]] = []
        with self.repo.database.transaction():
            sale = self.repo.get("sales", sale_id)
            if not sale or sale["status"] != "completed":
                raise ValidationError("Only completed sales can be returned.")
            return_id = self.repo.insert("returns", {
                "uuid": str(uuid.uuid4()), "return_number": self.repo.next_number(
                    utc_now().strftime("%Y%m%d"), "RET"),
                "sale_id": sale_id, "total_minor": 0, "note": note,
                "created_at": now, "created_by": user_id,
            })
            total = 0
            for request in items:
                sale_item_id = int(request["sale_item_id"])
                row = self.repo.get("sale_items", sale_item_id)
                if not row or row["sale_id"] != sale_id:
                    raise NotFoundError("Sale line was not found.")
                quantity = int(request["quantity_milli"])
                remaining = int(row["quantity_milli"]) - int(row["returned_milli"])
                if quantity <= 0 or quantity > remaining:
                    raise ValidationError("Returned quantity exceeds the unreturned quantity.")
                amount = int((Decimal(row["line_total_minor"] * quantity) / Decimal(row["quantity_milli"])).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
                total += amount
                self.repo.update("sale_items", sale_item_id, {"returned_milli": int(row["returned_milli"]) + quantity})
                should_restock = bool(request.get("restock", restock))
                was_restocked = bool(should_restock and row["item_type"] in {"product", "weighed"})
                if was_restocked and row["item_id"] is not None:
                    item_id = int(row["item_id"])
                    self.repo.stock_update(item_id, quantity, now)
                    self.repo.insert("stock_movements", {
                        "item_id": item_id, "quantity_delta_milli": quantity, "reason": "return",
                        "reference": str(return_id), "created_at": now, "created_by": user_id,
                    })
                    changed.append((item_id, int(self.repo.get("items", item_id)["stock_milli"])))
                self.repo.insert("return_items", {
                    "return_id": return_id, "sale_item_id": sale_item_id, "quantity_milli": quantity,
                    "amount_minor": amount, "restocked": int(was_restocked),
                })
            self.repo.update("returns", return_id, {"total_minor": total})
            return_row = self.repo.get("returns", return_id)
            self.repo.insert_outbox("returns", return_row["uuid"], "create", {
                "return_number": return_row["return_number"], "total_minor": total,
            }, now)
            self.repo.insert("audit_log", {
                "user_id": user_id, "action": "sale_returned", "entity": "returns",
                "entity_id": str(return_id),
                "details_json": json.dumps({"sale_id": sale_id, "total_minor": total}),
                "created_at": now,
            })
        for item_id, stock in changed:
            self.events.publish("stock_changed", item_id=item_id, stock_milli=stock)
        return self.repo.get("returns", return_id) or {}
