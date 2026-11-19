"""Setup, reporting, receipts, backups, and CSV import/export services."""

import csv
import io
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.core.errors import ImportErrorReport, NotFoundError, ValidationError
from backend.core.files import atomic_write
from backend.core.money import fmt, milli_to_qty
from backend.repositories.sqlite_repository import SqliteRepository
from backend.seed.presets import MODULE_KEYS, PRESETS
from backend.services.catalog import AuthService, CatalogService, CustomerService, SettingsService


class SetupService:
    """Apply business presets and create the initial administrator profile."""

    def __init__(self, repository: SqliteRepository, settings: SettingsService, auth: AuthService,
                 catalog: CatalogService) -> None:
        self.repo, self.settings, self.auth, self.catalog = repository, settings, auth, catalog

    def is_setup_complete(self) -> bool:
        """Return whether the first-run wizard has been completed."""
        return self.settings.get("setup_complete", "0") == "1"

    def list_presets(self) -> list[str]:
        """List supported business presets."""
        return list(PRESETS)

    def apply_preset(self, name: str) -> None:
        """Apply terminology, categories, modules, and payment methods atomically."""
        if name not in PRESETS:
            raise ValidationError("Unsupported business preset.")
        preset = PRESETS[name]
        with self.repo.database.transaction():
            self.settings.set_terminology(preset["terminology"])
            self.settings.set_modules({key: False for key in MODULE_KEYS})
            self.settings.set_modules(preset["modules"])
            self.settings.set("business_type", name)
            for category in preset["categories"]:
                if not self.repo.find("categories", {"name": category}, limit=1):
                    self.catalog.create_category(category)
            self.settings.set_payment_methods({"Cash": True, "M-Pesa": True, "Card": True, "Bank transfer": True})

    def complete_setup(
        self, business_name: str, business_type: str, currency: str,
        admin_username: str, admin_name: str, admin_password: str,
        sample_data: bool = False,
    ) -> int:
        """Save initial business settings and create the first administrator."""
        if not business_name.strip() or not currency.strip():
            raise ValidationError("Business name and currency are required.")
        if self.is_setup_complete():
            raise ValidationError("Initial setup has already been completed.")
        with self.repo.database.transaction():
            self.apply_preset(business_type)
            for key, value in {
                "business_name": business_name.strip(), "currency": currency.strip().upper(),
                "device_id": str(uuid.uuid4()),
            }.items():
                self.settings.set(key, value)
            user_id = self.auth.create_user(admin_username, admin_name, "Admin", admin_password)
            if sample_data:
                from backend.seed.demo_data import seed_business
                seed_business(self.catalog, business_type)
            self.settings.set("setup_complete", "1")
        self.auth.enforcement_enabled = True
        return user_id


class ReportService:
    """Produce summary reports from persisted sales and inventory."""

    def __init__(self, repository: SqliteRepository, auth: AuthService | None = None) -> None:
        self.repo, self.auth = repository, auth

    def _authorize(self) -> None:
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("reports.read")

    def dashboard_kpis(self, now: datetime | None = None) -> dict[str, int]:
        """Return today's sales, order count, customer count, and average order."""
        self._authorize()
        current = now or datetime.now(timezone.utc)
        start = current.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        totals = self.repo.daily_totals(start.isoformat(), end.isoformat())
        customers = len(self.repo.find("customers"))
        orders = totals["orders"]
        return {**totals, "customers": customers,
                "average_order_minor": totals["sales_minor"] // orders if orders else 0}

    def daily_report(self, day: str) -> dict[str, Any]:
        """Return sales and payment totals for one UTC date."""
        self._authorize()
        start = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        totals = self.repo.daily_totals(start.isoformat(), (start + timedelta(days=1)).isoformat())
        return {**totals, "payments": self.repo.payment_breakdown(start.isoformat(), (start + timedelta(days=1)).isoformat())}

    def monthly_report(self, year: int, month: int) -> dict[str, Any]:
        """Return sales totals and daily series for a UTC calendar month."""
        self._authorize()
        if not 1 <= month <= 12:
            raise ValidationError("Month must be between 1 and 12.")
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
        totals = self.repo.daily_totals(start.isoformat(), end.isoformat())
        return {**totals, "series": self.repo.sales_by_day(start.isoformat(), end.isoformat())}

    def sales_series(self, start: str, end: str) -> list[dict[str, Any]]:
        """Return sales grouped by UTC date."""
        self._authorize()
        return self.repo.sales_by_day(start, end)

    def range_report(self, start: str, end: str) -> dict[str, Any]:
        """Return totals, daily series, and breakdowns for an ISO timestamp range."""
        self._authorize()
        try:
            start_at = datetime.fromisoformat(start)
            end_at = datetime.fromisoformat(end)
        except ValueError as error:
            raise ValidationError("Report dates must be valid ISO dates or timestamps.") from error
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
        if end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
        start_at = start_at.astimezone(timezone.utc)
        end_at = end_at.astimezone(timezone.utc)
        if end_at <= start_at:
            raise ValidationError("Report end must be later than its start.")
        start_text, end_text = start_at.isoformat(), end_at.isoformat()
        return {
            **self.repo.daily_totals(start_text, end_text),
            "payments": self.repo.payment_breakdown(start_text, end_text),
            "item_types": self.repo.item_type_breakdown(start_text, end_text),
            "series": self.repo.sales_by_day(start_text, end_text),
        }

    def top_items(self, start: str, end: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return best-selling item snapshots."""
        self._authorize()
        return self.repo.top_items(start, end, limit)

    def breakdowns(self, start: str, end: str) -> dict[str, list[dict[str, Any]]]:
        """Return payment-method and item-type sales breakdowns."""
        self._authorize()
        return {
            "payments": self.repo.payment_breakdown(start, end),
            "item_types": self.repo.item_type_breakdown(start, end),
        }

    def stock_valuation(self) -> dict[str, int]:
        """Return cost and retail stock valuations."""
        self._authorize()
        return self.repo.stock_valuation()

    def export_sales_csv(self, start: str, end: str, path: Path) -> Path:
        """Write sales rows to a UTF-8 CSV using atomic replacement."""
        self._authorize()
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(("receipt_number", "created_at", "status", "subtotal_minor", "discount_minor", "tax_minor", "total_minor"))
        for sale in self.repo.find("sales", order_by="created_at"):
            if start <= sale["created_at"] < end:
                writer.writerow(tuple(sale[key] for key in
                                      ("receipt_number", "created_at", "status", "subtotal_minor", "discount_minor", "tax_minor", "total_minor")))
        atomic_write(path, stream.getvalue().encode("utf-8-sig"))
        return path


class ReceiptService:
    """Build receipt data and render it as plain text."""

    def __init__(self, repository: SqliteRepository, settings: SettingsService) -> None:
        self.repo, self.settings = repository, settings

    def build_receipt(self, sale_id: int) -> dict[str, Any]:
        """Build a receipt from immutable sale and item snapshots."""
        sale = self.repo.get("sales", sale_id)
        if not sale:
            raise NotFoundError("Sale was not found.")
        items = self.repo.find("sale_items", {"sale_id": sale_id}, order_by="id")
        payments = self.repo.find("sale_payments", {"sale_id": sale_id}, order_by="id")
        customer = self.repo.get("customers", sale["customer_id"]) if sale["customer_id"] else None
        return {"business_name": self.settings.get("business_name", "Business"),
                "currency": self.settings.get("currency", "KES"), "sale": sale,
                "items": items, "payments": payments, "customer": customer}

    def render_text(self, sale_id: int, width: int = 42) -> str:
        """Render a compact thermal-style text receipt."""
        if width < 24:
            raise ValidationError("Receipt width must be at least 24 characters.")
        receipt = self.build_receipt(sale_id)
        sale = receipt["sale"]
        currency = receipt["currency"]
        lines = [
            receipt["business_name"].center(width),
            sale["receipt_number"].center(width),
            str(sale["created_at"]).replace("T", " ").center(width),
        ]
        if receipt["customer"]:
            lines.append(f"Customer: {receipt['customer']['name']}"[:width])
        lines.append("-" * width)
        for item in receipt["items"]:
            qty = milli_to_qty(item["quantity_milli"]).normalize()
            lines.append(str(item["name_snapshot"])[:width])
            details = f"{qty:g} x {fmt(item['unit_price_minor'], currency)}"
            amount = fmt(item["line_total_minor"], currency)
            lines.append(self._receipt_row(details, amount, width))
        lines.append("-" * width)
        for label, amount_minor in (
            ("Subtotal", sale["subtotal_minor"]),
            ("Discount", sale["discount_minor"]),
            ("Tax", sale["tax_minor"]),
        ):
            lines.append(self._receipt_row(label, fmt(amount_minor, currency), width))
        lines.append(self._receipt_row("TOTAL", fmt(sale["total_minor"], currency), width))
        lines.append("-" * width)
        lines.append("Payment".center(width))
        for payment in receipt["payments"]:
            lines.append(self._receipt_row(
                payment["method"], fmt(payment["amount_minor"], currency), width,
            ))
        if int(sale["change_minor"]):
            lines.append(self._receipt_row(
                "Change", fmt(sale["change_minor"], currency), width,
            ))
        lines.extend(("-" * width, "Thank you for shopping with us".center(width)))
        return "\n".join(lines)

    def export_text(self, sale_id: int, path: Path, width: int = 42) -> Path:
        """Atomically save the persisted receipt as UTF-8 text."""
        atomic_write(path, self.render_text(sale_id, width).encode("utf-8"))
        return path

    @staticmethod
    def _receipt_row(label: str, amount: str, width: int) -> str:
        """Align receipt labels and amounts within the requested paper width."""
        if len(amount) >= width:
            return amount
        label_width = width - len(amount) - 1
        return f"{label[:label_width]:<{label_width}} {amount}"


class BackupService:
    """Create, list, and restore local SQLite database backups."""

    def __init__(self, repository: SqliteRepository, backup_dir: Path, auth: AuthService | None = None) -> None:
        self.repo, self.backup_dir, self.auth = repository, backup_dir, auth
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _authorize(self) -> None:
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("data.backup")

    def create_backup(self) -> Path:
        """Create a consistent SQLite snapshot."""
        self._authorize()
        path = self.backup_dir / f"pos-{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}.db"
        target = sqlite3.connect(path)
        try:
            self.repo.database.connection.backup(target)
        finally:
            target.close()
        return path

    def list_backups(self) -> list[Path]:
        """List database backups newest first."""
        self._authorize()
        return sorted(self.backup_dir.glob("pos-*.db"), reverse=True)

    def restore_backup(self, path: Path) -> None:
        """Restore a validated local backup into the current database."""
        self._authorize()
        resolved = path.resolve()
        if resolved.parent != self.backup_dir.resolve() or not resolved.is_file():
            raise ValidationError("Backup file is outside the managed backup directory.")
        source = sqlite3.connect(resolved)
        try:
            integrity = source.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValidationError("Backup database failed its integrity check.")
            self.create_backup()
            source.backup(self.repo.database.connection)
        finally:
            source.close()


class ImportExportService:
    """Validate CSV data before applying changes and export catalogue records."""

    ITEM_HEADERS = {"name", "price_minor", "quantity_milli"}

    def __init__(self, repository: SqliteRepository, catalog: CatalogService,
                 customers: CustomerService | None = None, auth: AuthService | None = None) -> None:
        self.repo, self.catalog, self.customers, self.auth = repository, catalog, customers, auth

    def _authorize(self, permission: str) -> None:
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission(permission)

    def preview_items_csv(self, content: str) -> dict[str, Any]:
        """Parse CSV into valid rows and row-numbered errors without writing."""
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or not self.ITEM_HEADERS.issubset(reader.fieldnames):
            raise ValidationError("CSV headers must include name, price_minor, and quantity_milli.")
        rows: list[dict[str, str]] = []
        errors: list[dict[str, object]] = []
        for row_number, row in enumerate(reader, 2):
            try:
                if not row.get("name", "").strip():
                    raise ValueError("name is required")
                if int(row["price_minor"]) < 0 or int(row["quantity_milli"]) < 0:
                    raise ValueError("price and quantity must be nonnegative")
                if row.get("barcode") and self.repo.find("items", {"barcode": row["barcode"]}, limit=1):
                    raise ValueError("barcode already exists")
                rows.append({**{key: value or "" for key, value in row.items()},
                             "__row__": str(row_number)})
            except (ValueError, TypeError) as error:
                errors.append({"row": row_number, "message": str(error)})
        return {"rows": rows, "errors": errors}

    def preview_customers_csv(self, content: str) -> dict[str, Any]:
        """Parse customer CSV rows without writing customer records."""
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or "name" not in reader.fieldnames:
            raise ValidationError("Customer CSV must include a name column.")
        rows: list[dict[str, str]] = []
        errors: list[dict[str, object]] = []
        seen_phones: set[str] = set()
        for row_number, row in enumerate(reader, 2):
            name, phone = (row.get("name") or "").strip(), (row.get("phone") or "").strip()
            if not name:
                errors.append({"row": row_number, "message": "name is required"})
                continue
            if phone and (phone in seen_phones or self.repo.find("customers", {"phone": phone}, limit=1)):
                errors.append({"row": row_number, "message": "phone already exists"})
                continue
            if phone:
                seen_phones.add(phone)
            rows.append({**{key: value or "" for key, value in row.items()},
                         "__row__": str(row_number)})
        return {"rows": rows, "errors": errors}

    def import_customers_csv(self, content: str, dry_run: bool = True) -> dict[str, Any]:
        """Preview or register customer CSV rows transactionally."""
        if self.customers is None:
            raise ValidationError("Customer import is not configured.")
        if not dry_run:
            self._authorize("customers.write")
        preview = self.preview_customers_csv(content)
        if preview["errors"]:
            raise ImportErrorReport(preview["errors"])
        if dry_run:
            return preview
        created: list[int] = []
        with self.repo.database.transaction():
            for row in preview["rows"]:
                created.append(self.customers.register(
                    row["name"], row.get("phone", ""), row.get("email", ""), row.get("notes", "")
                ))
        return {"rows": preview["rows"], "errors": [], "created_ids": created}

    def import_items_csv(self, content: str, dry_run: bool = True) -> dict[str, Any]:
        """Preview or import item rows; reject the whole import on invalid rows."""
        if not dry_run:
            self._authorize("catalog.write")
        preview = self.preview_items_csv(content)
        if preview["errors"]:
            raise ImportErrorReport(preview["errors"])
        if dry_run:
            return preview
        created: list[int] = []
        with self.repo.database.transaction():
            for row in preview["rows"]:
                created.append(self.catalog.create_item(
                    row["name"], int(row["price_minor"]),
                    stock_milli=int(row["quantity_milli"]),
                    barcode=row.get("barcode") or None,
                    category_id=int(row["category_id"]) if row.get("category_id") else None,
                ))
        return {"rows": preview["rows"], "errors": [], "created_ids": created}

    def export_items_csv(self, path: Path) -> Path:
        """Export active items to a stable CSV format."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("catalog.read")
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(("id", "name", "barcode", "price_minor", "cost_minor", "stock_milli", "item_type"))
        for item in self.repo.find("items", {"archived": 0}, order_by="id"):
            writer.writerow(tuple(item[key] for key in
                                  ("id", "name", "barcode", "price_minor", "cost_minor", "stock_milli", "item_type")))
        atomic_write(path, output.getvalue().encode("utf-8-sig"))
        return path

    def export_customers_csv(self, path: Path) -> Path:
        """Export customer contact records to CSV."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("customers.read")
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(("id", "name", "phone", "email", "notes", "credit_minor"))
        for customer in self.repo.find("customers", order_by="name"):
            writer.writerow(tuple(customer[key] for key in
                                  ("id", "name", "phone", "email", "notes", "credit_minor")))
        atomic_write(path, output.getvalue().encode("utf-8-sig"))
        return path
