"""Settings, authentication, catalogue, inventory, customer, and voucher services."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.core.errors import (
    AccountLockedError, AuthenticationError, NotFoundError, PermissionDeniedError,
    ValidationError, VoucherError,
)
from backend.core.events import EventBus
from backend.core.files import copy_image
from backend.core.security import PBKDF2_ITERATIONS, hash_password, hash_pin, verify_password
from backend.models.records import UserContext
from backend.repositories.sqlite_repository import SqliteRepository

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "Admin": {"*"},
    "Manager": {"catalog.read", "catalog.write", "inventory.adjust", "customers.write",
                "inventory.read", "customers.read", "sales.process", "sales.read",
                "sales.return", "reports.read", "discounts.write"},
    "Cashier": {"catalog.read", "inventory.read", "customers.read",
                "customers.write", "sales.process", "sales.read"},
}
ITEM_TYPES = {"product", "service", "weighed", "bundle", "non_inventory"}


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def timestamp() -> str:
    """Return the current UTC timestamp in ISO-8601 form."""
    return utc_now().isoformat(timespec="seconds")


class SettingsService:
    """Manage profile, terminology, modules, taxes, and payment settings."""

    def __init__(
        self, repository: SqliteRepository, events: EventBus,
        auth: AuthService | None = None,
    ) -> None:
        self.repo, self.events, self.auth = repository, events, auth

    def _authorize(self) -> None:
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("settings.manage")

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return a setting value."""
        row = self.repo.get("settings", key)
        return str(row["value"]) if row else default

    def set(self, key: str, value: str) -> None:
        """Create or update a generic setting."""
        self._authorize()
        with self.repo.database.transaction():
            if self.repo.get("settings", key):
                self.repo.update("settings", key, {"value": value})
            else:
                self.repo.insert("settings", {"key": key, "value": value})
        self.repo.database.after_commit(lambda: self.events.publish("settings_changed", key=key))

    def profile(self) -> dict[str, str]:
        """Return configured business profile values."""
        return {row["key"]: row["value"] for row in self.repo.find("settings")}

    def terminology(self) -> dict[str, str]:
        """Return all terminology overrides."""
        return {row["key"]: row["value"] for row in self.repo.find("terminology")}

    def term(self, key: str, default: str | None = None) -> str:
        """Resolve a terminology key, falling back only when explicitly supplied."""
        row = self.repo.get("terminology", key)
        if row:
            return str(row["value"])
        if default is not None:
            return default
        raise NotFoundError(f"Terminology key '{key}' is not configured.")

    def set_terminology(self, values: dict[str, str]) -> None:
        """Replace terminology values and publish a change event."""
        self._authorize()
        with self.repo.database.transaction():
            for key, value in values.items():
                if self.repo.get("terminology", key):
                    self.repo.update("terminology", key, {"value": value})
                else:
                    self.repo.insert("terminology", {"key": key, "value": value})
        self.repo.database.after_commit(
            lambda: self.events.publish("terminology_changed", keys=tuple(values))
        )

    def modules(self) -> dict[str, bool]:
        """Return enabled module flags."""
        return {row["key"]: bool(row["enabled"]) for row in self.repo.find("modules")}

    def set_modules(self, modules: dict[str, bool]) -> None:
        """Persist module flags."""
        self._authorize()
        with self.repo.database.transaction():
            for key, enabled in modules.items():
                values = {"enabled": int(enabled)}
                if self.repo.get("modules", key):
                    self.repo.update("modules", key, values)
                else:
                    self.repo.insert("modules", {"key": key, **values})
        self.repo.database.after_commit(
            lambda: self.events.publish("settings_changed", key="modules")
        )

    def set_tax_rate(self, name: str, rate_basis_points: int, is_default: bool = False) -> int:
        """Create or update a tax rate."""
        self._authorize()
        if rate_basis_points < 0:
            raise ValidationError("Tax rate cannot be negative.")
        with self.repo.database.transaction():
            if is_default:
                for existing in self.repo.find("tax_rates"):
                    if existing["is_default"]:
                        self.repo.update("tax_rates", existing["id"], {"is_default": 0})
            found = self.repo.find("tax_rates", {"name": name}, limit=1)
            values = {"rate_basis_points": rate_basis_points, "is_default": int(is_default)}
            if found:
                self.repo.update("tax_rates", found[0]["id"], values)
                result = int(found[0]["id"])
            else:
                result = self.repo.insert("tax_rates", {"name": name, **values})
        self.repo.database.after_commit(lambda: self.events.publish("settings_changed", key="tax_rates"))
        return result

    def set_payment_methods(self, methods: dict[str, bool]) -> None:
        """Create or activate/deactivate payment methods."""
        self._authorize()
        with self.repo.database.transaction():
            for name, active in methods.items():
                found = self.repo.find("payment_methods", {"name": name}, limit=1)
                if found:
                    self.repo.update("payment_methods", found[0]["id"], {"active": int(active)})
                else:
                    self.repo.insert("payment_methods", {"name": name, "active": int(active)})
        self.repo.database.after_commit(lambda: self.events.publish("settings_changed", key="payment_methods"))

    def tax_rates(self) -> list[dict[str, Any]]:
        """List active tax-rate definitions."""
        return self.repo.find("tax_rates", {"active": 1}, order_by="name")

    def payment_methods(self) -> list[dict[str, Any]]:
        """List active payment methods."""
        return self.repo.find("payment_methods", {"active": 1}, order_by="name")


class AuthService:
    """Authenticate staff and enforce role permissions in service methods."""

    def __init__(self, repository: SqliteRepository) -> None:
        self.repo = repository
        self._current_user: UserContext | None = None
        self.enforcement_enabled = False

    @property
    def current_user(self) -> UserContext | None:
        """Return the active user context."""
        return self._current_user

    def create_user(
        self, username: str, display_name: str, role: str, password: str, pin: str | None = None
    ) -> int:
        """Create a staff account with a salted password and optional PIN."""
        if self.enforcement_enabled:
            self.require_permission("users.manage")
        if role not in ROLE_PERMISSIONS or not username.strip() or not display_name.strip():
            raise ValidationError("Username, display name, and a supported role are required.")
        salt, digest = hash_password(password)
        pin_salt, pin_digest = hash_pin(pin) if pin else ("", "")
        now, user_uuid = timestamp(), str(uuid.uuid4())
        with self.repo.database.transaction():
            user_id = self.repo.insert("users", {
                "uuid": user_uuid, "username": username.strip().lower(),
                "display_name": display_name.strip(), "role": role, "salt": salt,
                "password_hash": digest, "hash_iterations": PBKDF2_ITERATIONS,
                "pin_salt": pin_salt, "pin_hash": pin_digest, "created_at": now,
            })
            self.repo.insert_outbox("users", user_uuid, "create", {
                "id": user_id, "username": username.strip().lower()
            }, now)
        return user_id

    def login(self, username: str, password: str) -> UserContext:
        """Authenticate an active user and apply the five-attempt lockout."""
        found = self.repo.find("users", {"username": username.strip().lower()}, limit=1)
        if not found:
            raise AuthenticationError("Username or password is incorrect.")
        user = found[0]
        now = utc_now()
        locked_until = datetime.fromisoformat(user["locked_until"]) if user["locked_until"] else None
        if locked_until and locked_until > now:
            raise AccountLockedError("Account is temporarily locked.", locked_until=user["locked_until"])
        valid = bool(user["active"]) and verify_password(
            password, user["salt"], user["password_hash"], user["hash_iterations"]
        )
        if not valid:
            failures = int(user["failed_logins"]) + 1
            lock_time = (now + timedelta(minutes=5)).isoformat(timespec="seconds") if failures >= 5 else None
            self.repo.update("users", user["id"], {
                "failed_logins": 0 if lock_time else failures,
                "locked_until": lock_time,
            })
            if lock_time:
                raise AccountLockedError("Account is temporarily locked.", locked_until=lock_time)
            raise AuthenticationError("Username or password is incorrect.")
        self.repo.update("users", user["id"], {"failed_logins": 0, "locked_until": None})
        context = UserContext(user["id"], user["username"], user["display_name"], user["role"],
                              bool(user["must_change_password"]))
        self._current_user = context
        return context

    def logout(self) -> None:
        """Clear the current authenticated user."""
        self._current_user = None

    def require_permission(self, permission: str, user: UserContext | None = None) -> None:
        """Raise when the active user does not have the requested permission."""
        active = user or self._current_user
        if active is None or permission not in ROLE_PERMISSIONS.get(active.role, set()) and "*" not in ROLE_PERMISSIONS.get(active.role, set()):
            raise PermissionDeniedError("You do not have permission to perform this action.")

    def verify_admin_pin(self, pin: str) -> bool:
        """Verify the configured PIN of the current administrator."""
        if self._current_user is None or self._current_user.role != "Admin":
            raise PermissionDeniedError("Administrator access is required.")
        user = self.repo.get("users", self._current_user.id)
        return bool(user and user["pin_hash"] and verify_password(pin, user["pin_salt"], user["pin_hash"]))

    def list_users(self) -> list[dict[str, Any]]:
        """List staff accounts without exposing password material."""
        self.require_permission("users.manage")
        return [
            {key: value for key, value in row.items()
             if key not in {"salt", "password_hash", "pin_salt", "pin_hash"}}
            for row in self.repo.find("users", order_by="username")
        ]

    def update_user(self, user_id: int, **fields: Any) -> None:
        """Update allowed staff profile, role, or active status."""
        self.require_permission("users.manage")
        allowed = {"display_name", "role", "active"}
        if not fields or set(fields) - allowed:
            raise ValidationError("Unsupported user update.")
        if "role" in fields and fields["role"] not in ROLE_PERMISSIONS:
            raise ValidationError("Unsupported user role.")
        if self._current_user and self._current_user.id == user_id and fields.get("active") == 0:
            raise ValidationError("You cannot deactivate your own account.")
        user = self.repo.get("users", user_id)
        if not user:
            raise NotFoundError("User was not found.")
        now = timestamp()
        with self.repo.database.transaction():
            self.repo.update("users", user_id, fields)
            self.repo.insert_outbox("users", user["uuid"], "update", fields, now)

    def update_profile(
        self, current_password: str, username: str, display_name: str,
        new_password: str | None = None,
    ) -> None:
        """Update the signed-in administrator's own identity and optional password."""
        active = self._current_user
        if active is None:
            raise AuthenticationError("Log in before updating your profile.")
        if active.role != "Admin":
            raise PermissionDeniedError("Administrator access is required.")
        user = self.repo.get("users", active.id)
        if not user or not verify_password(
            current_password, user["salt"], user["password_hash"], user["hash_iterations"]
        ):
            raise AuthenticationError("Current password is incorrect.")

        normalized_username = username.strip().lower()
        normalized_name = display_name.strip()
        if not normalized_username or not normalized_name:
            raise ValidationError("Username and display name are required.")

        fields: dict[str, Any] = {
            "username": normalized_username,
            "display_name": normalized_name,
        }
        password_changed = new_password is not None
        if password_changed:
            salt, digest = hash_password(new_password)
            fields.update({
                "salt": salt,
                "password_hash": digest,
                "hash_iterations": PBKDF2_ITERATIONS,
                "must_change_password": 0,
            })

        now = timestamp()
        with self.repo.database.transaction():
            self.repo.update("users", active.id, fields)
            self.repo.insert_outbox("users", user["uuid"], "update", {
                "username": normalized_username,
                "display_name": normalized_name,
            }, now)
        self._current_user = UserContext(
            active.id, normalized_username, normalized_name, active.role,
            False if password_changed else active.must_change_password,
        )

    def change_password(self, old_password: str, new_password: str) -> None:
        """Change the active user's password and clear the forced-change flag."""
        if self._current_user is None:
            raise AuthenticationError("Log in before changing the password.")
        user = self.repo.get("users", self._current_user.id)
        if not user or not verify_password(old_password, user["salt"], user["password_hash"], user["hash_iterations"]):
            raise AuthenticationError("Current password is incorrect.")
        salt, digest = hash_password(new_password)
        self.repo.update("users", user["id"], {
            "salt": salt, "password_hash": digest, "hash_iterations": PBKDF2_ITERATIONS,
            "must_change_password": 0,
        })
        self._current_user = UserContext(
            self._current_user.id, self._current_user.username,
            self._current_user.display_name, self._current_user.role, False,
        )


class CatalogService:
    """Register, edit, archive, and search catalogue items and categories."""

    def __init__(
        self, repository: SqliteRepository, events: EventBus,
        auth: AuthService | None = None, assets_dir: Path | None = None,
    ) -> None:
        self.repo, self.events, self.auth = repository, events, auth
        self.assets_dir = assets_dir

    def _authorize(self, permission: str) -> None:
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission(permission)

    def create_category(self, name: str, parent_id: int | None = None) -> int:
        """Create a catalogue category."""
        self._authorize("catalog.write")
        if not name.strip():
            raise ValidationError("Category name is required.")
        with self.repo.database.transaction():
            category_id = self.repo.insert("categories", {
                "name": name.strip(), "parent_id": parent_id, "created_at": timestamp()
            })
        self.repo.database.after_commit(
            lambda: self.events.publish("catalog_changed", category_id=category_id)
        )
        return category_id

    def list_categories(self) -> list[dict[str, Any]]:
        """List catalogue categories for filters and management views."""
        self._authorize("catalog.read")
        return self.repo.find("categories", order_by="name")

    def create_item(self, name: str, price_minor: int, **fields: Any) -> int:
        """Create an item with server-validated money and inventory fields."""
        self._authorize("catalog.write")
        item_type = fields.pop("item_type", "product")
        if not name.strip() or item_type not in ITEM_TYPES:
            raise ValidationError("A name and supported item type are required.")
        cost_minor = fields.pop("cost_minor", 0)
        stock_milli = fields.pop("stock_milli", 0)
        low_stock_milli = fields.pop("low_stock_milli", 0)
        if min(price_minor, cost_minor, stock_milli, low_stock_milli) < 0:
            raise ValidationError("Prices and stock quantities cannot be negative.")
        allowed = {"description", "category_id", "unit", "barcode", "tax_rate_id", "tax_inclusive"}
        if set(fields) - allowed:
            raise ValidationError("Unsupported item fields were supplied.")
        now, item_uuid = timestamp(), str(uuid.uuid4())
        with self.repo.database.transaction():
            item_id = self.repo.insert("items", {
                "uuid": item_uuid, "name": name.strip(), "item_type": item_type,
                "price_minor": price_minor, "cost_minor": cost_minor,
                "stock_milli": 0, "low_stock_milli": low_stock_milli,
                "created_at": now, "updated_at": now, **fields,
            })
            if stock_milli and item_type in {"product", "weighed", "bundle"}:
                self.repo.stock_update(item_id, stock_milli, now)
                self.repo.insert("stock_movements", {
                    "item_id": item_id, "quantity_delta_milli": stock_milli,
                    "reason": "opening_balance", "created_at": now,
                })
            self.repo.insert_outbox("items", item_uuid, "create", {"id": item_id, "name": name}, now)
        self.repo.database.after_commit(
            lambda: self.events.publish("stock_changed", item_id=item_id)
        )
        self.repo.database.after_commit(
            lambda: self.events.publish("catalog_changed", item_id=item_id)
        )
        return item_id

    def update_item(self, item_id: int, **fields: Any) -> None:
        """Update allowed catalogue properties."""
        self._authorize("catalog.write")
        allowed = {"name", "description", "category_id", "item_type", "unit", "barcode",
                   "price_minor", "cost_minor", "tax_rate_id", "tax_inclusive", "low_stock_milli"}
        if not fields or set(fields) - allowed:
            raise ValidationError("Unsupported or empty item update.")
        item = self.repo.get("items", item_id)
        if not item or item["archived"]:
            raise NotFoundError("Item was not found.")
        if "item_type" in fields and fields["item_type"] not in ITEM_TYPES:
            raise ValidationError("Unsupported item type.")
        if "item_type" in fields and item["stock_milli"] and fields["item_type"] not in {"product", "weighed", "bundle"}:
            raise ValidationError("Stock must be adjusted before changing to a non-inventory item type.")
        for key in ("price_minor", "cost_minor", "low_stock_milli"):
            if key in fields and fields[key] < 0:
                raise ValidationError("Prices and stock thresholds cannot be negative.")
        fields["updated_at"] = timestamp()
        with self.repo.database.transaction():
            self.repo.update("items", item_id, fields)
            self.repo.insert_outbox("items", item["uuid"], "update", fields, fields["updated_at"])
        self.repo.database.after_commit(
            lambda: self.events.publish("catalog_changed", item_id=item_id)
        )

    def set_item_image(self, item_id: int, source: Path) -> str:
        """Validate and copy a product image into managed local storage."""
        self._authorize("catalog.write")
        item = self.repo.get("items", item_id)
        if not item or item["archived"]:
            raise NotFoundError("Item was not found.")
        if self.assets_dir is None:
            raise ValidationError("Product image storage is not configured.")
        copied = copy_image(source, self.assets_dir)
        now = timestamp()
        try:
            with self.repo.database.transaction():
                self.repo.update("items", item_id, {
                    "image_path": str(copied), "updated_at": now,
                })
                self.repo.insert_outbox(
                    "items", item["uuid"], "update", {"image_path": copied.name}, now,
                )
        except Exception:
            copied.unlink(missing_ok=True)
            raise
        self.repo.database.after_commit(
            lambda: self.events.publish("catalog_changed", item_id=item_id)
        )
        return str(copied)

    def archive_item(self, item_id: int) -> None:
        """Archive an item without deleting sales history."""
        self._authorize("catalog.write")
        item = self.repo.get("items", item_id)
        if not item:
            raise NotFoundError("Item was not found.")
        now = timestamp()
        with self.repo.database.transaction():
            self.repo.update("items", item_id, {"archived": 1, "updated_at": now})
            self.repo.insert_outbox("items", item["uuid"], "archive", {"archived": True}, now)
        self.repo.database.after_commit(
            lambda: self.events.publish("catalog_changed", item_id=item_id)
        )

    def search_items(self, query: str = "", category_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Search active catalogue items."""
        self._authorize("catalog.read")
        filters = {"archived": 0}
        if category_id is not None:
            filters["category_id"] = category_id
        return self.repo.find("items", filters, query, ("name", "barcode"), "name", limit=limit)

    def find_by_barcode(self, barcode: str) -> dict[str, Any]:
        """Resolve an active item by exact barcode."""
        self._authorize("catalog.read")
        rows = self.repo.find("items", {"barcode": barcode, "archived": 0}, limit=1)
        if not rows:
            raise NotFoundError("No item matches that barcode.")
        return rows[0]

    def set_bundle_components(self, bundle_id: int, components: list[dict[str, int]]) -> None:
        """Replace the component recipe for a bundle and reject recursive bundles."""
        self._authorize("catalog.write")
        bundle = self.repo.get("items", bundle_id)
        if not bundle or bundle["item_type"] != "bundle":
            raise ValidationError("Components can only be assigned to a bundle.")
        normalized: list[tuple[int, int]] = []
        graph: dict[int, set[int]] = {}
        for item in self.repo.find("item_components"):
            graph.setdefault(int(item["item_id"]), set()).add(int(item["component_id"]))
        graph.pop(bundle_id, None)
        for component in components:
            component_id = int(component["item_id"])
            quantity = int(component["quantity_milli"])
            child = self.repo.get("items", component_id)
            if not child or child["archived"] or component_id == bundle_id or quantity <= 0:
                raise ValidationError("Bundle component or quantity is invalid.")
            if child["item_type"] in {"service", "non_inventory"}:
                raise ValidationError("Bundle components must track inventory.")
            graph.setdefault(bundle_id, set()).add(component_id)
            normalized.append((component_id, quantity))
        def reaches_root(node: int, visited: set[int]) -> bool:
            if node == bundle_id:
                return True
            if node in visited:
                return False
            visited.add(node)
            return any(reaches_root(child, visited) for child in graph.get(node, set()))
        if any(reaches_root(component_id, set()) for component_id, _ in normalized):
            raise ValidationError("Bundle recipes cannot contain a cycle.")
        with self.repo.database.transaction():
            self.repo.replace_bundle_components(bundle_id, normalized)


class InventoryService:
    """Apply stock changes through an auditable append-only movement ledger."""

    def __init__(self, repository: SqliteRepository, events: EventBus, auth: AuthService | None = None) -> None:
        self.repo, self.events, self.auth = repository, events, auth

    def adjust_stock(self, item_id: int, quantity_delta_milli: int, reason: str, user_id: int | None = None) -> int:
        """Apply a signed quantity adjustment and append a stock movement."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("inventory.adjust")
        if not reason.strip() or quantity_delta_milli == 0:
            raise ValidationError("A nonzero adjustment and reason are required.")
        return self._apply(item_id, quantity_delta_milli, reason, user_id)

    def restock(self, item_id: int, quantity_milli: int, user_id: int | None = None) -> int:
        """Increase inventory quantity."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("inventory.adjust")
        if quantity_milli <= 0:
            raise ValidationError("Restock quantity must be positive.")
        return self._apply(item_id, quantity_milli, "restock", user_id)

    def _apply(self, item_id: int, delta: int, reason: str, user_id: int | None) -> int:
        now = timestamp()
        with self.repo.database.transaction():
            item = self.repo.get("items", item_id)
            if not item or item["archived"]:
                raise NotFoundError("Item was not found.")
            if item["item_type"] not in {"product", "weighed", "bundle"}:
                raise ValidationError("This item type does not track stock.")
            previous = int(item["stock_milli"])
            if not self.repo.stock_update(item_id, delta, now):
                from backend.core.errors import InsufficientStockError
                raise InsufficientStockError("Stock cannot become negative.", item_id=item_id)
            self.repo.insert("stock_movements", {
                "item_id": item_id, "quantity_delta_milli": delta, "reason": reason,
                "created_at": now, "created_by": user_id,
            })
            self.repo.insert("audit_log", {
                "user_id": user_id, "action": "stock_adjusted", "entity": "items",
                "entity_id": str(item_id),
                "details_json": json.dumps({"delta_milli": delta, "reason": reason}),
                "created_at": now,
            })
            self.repo.insert_outbox(
                "items", item["uuid"], "update", {"stock_milli": previous + delta}, now
            )
            new_stock = previous + delta
        self.repo.database.after_commit(
            lambda: self.events.publish("stock_changed", item_id=item_id, stock_milli=new_stock)
        )
        threshold = int(item["low_stock_milli"])
        if threshold and previous > threshold >= new_stock:
            self.repo.database.after_commit(
                lambda: self.events.publish("low_stock_alert", item_id=item_id, stock_milli=new_stock)
            )
        return new_stock

    def low_stock_items(self) -> list[dict[str, Any]]:
        """Return active tracked items at or below their configured threshold."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("inventory.read")
        return [row for row in self.repo.find("items", {"archived": 0})
                if row["item_type"] in {"product", "weighed", "bundle"}
                and row["low_stock_milli"] > 0 and row["stock_milli"] <= row["low_stock_milli"]]

    def add_expiry_batch(self, item_id: int, batch_code: str, expiry_date: str, quantity_milli: int) -> int:
        """Record a dated batch for a tracked item."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("inventory.adjust")
        if quantity_milli <= 0:
            raise ValidationError("Batch quantity must be positive.")
        item = self.repo.get("items", item_id)
        if not item or item["item_type"] not in {"product", "weighed"}:
            raise ValidationError("Expiry batches require a tracked product.")
        try:
            from datetime import date
            date.fromisoformat(expiry_date)
        except ValueError as error:
            raise ValidationError("Expiry date must use YYYY-MM-DD.") from error
        now = timestamp()
        with self.repo.database.transaction():
            batch_id = self.repo.insert("expiry_batches", {
                "item_id": item_id, "batch_code": batch_code, "expiry_date": expiry_date,
                "quantity_milli": quantity_milli,
            })
            if not self.repo.stock_update(item_id, quantity_milli, now):
                raise ValidationError("Could not update batch stock.")
            self.repo.insert("stock_movements", {
                "item_id": item_id, "quantity_delta_milli": quantity_milli,
                "reason": "expiry_batch", "reference": str(batch_id), "created_at": now,
            })
        self.repo.database.after_commit(lambda: self.events.publish("stock_changed", item_id=item_id))
        return batch_id

    def expiring_items(self, days: int = 30) -> list[dict[str, Any]]:
        """Return non-empty batches expiring within the requested number of days."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("inventory.read")
        from datetime import date, timedelta
        if days < 0:
            raise ValidationError("Expiry horizon cannot be negative.")
        through = (date.today() + timedelta(days=days)).isoformat()
        return self.repo.expiring_batches(through)

    def stock_history(self, item_id: int) -> list[dict[str, Any]]:
        """Return stock ledger entries in chronological order."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("inventory.read")
        return self.repo.find("stock_movements", {"item_id": item_id}, order_by="id")

    def rebuild_stock_from_ledger(self) -> None:
        """Recompute cached balances from append-only stock movements."""
        with self.repo.database.transaction():
            for item in self.repo.find("items"):
                total = sum(row["quantity_delta_milli"] for row in self.repo.find("stock_movements", {"item_id": item["id"]}))
                self.repo.update("items", item["id"], {"stock_milli": total})
        self.events.publish("stock_changed", rebuilt=True)


class CustomerService:
    """Register customers and retrieve their purchase history."""

    def __init__(self, repository: SqliteRepository, auth: AuthService | None = None) -> None:
        self.repo, self.auth = repository, auth

    def register(self, name: str, phone: str = "", email: str = "", notes: str = "") -> int:
        """Create a customer record."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("customers.write")
        if not name.strip():
            raise ValidationError("Customer name is required.")
        now, customer_uuid = timestamp(), str(uuid.uuid4())
        with self.repo.database.transaction():
            customer_id = self.repo.insert("customers", {
                "uuid": customer_uuid, "name": name.strip(), "phone": phone.strip(),
                "email": email.strip(), "notes": notes.strip(), "created_at": now,
            })
            self.repo.insert_outbox("customers", customer_uuid, "create", {"id": customer_id}, now)
        return customer_id

    def update(self, customer_id: int, **fields: str) -> None:
        """Update customer contact or note fields."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("customers.write")
        if not fields or set(fields) - {"name", "phone", "email", "notes"}:
            raise ValidationError("Unsupported customer update.")
        customer = self.repo.get("customers", customer_id)
        if not customer:
            raise NotFoundError("Customer was not found.")
        with self.repo.database.transaction():
            self.repo.update("customers", customer_id, fields)
            self.repo.insert_outbox(
                "customers", customer["uuid"], "update", fields, timestamp()
            )

    def delete(self, customer_id: int) -> None:
        """Delete customer details without deleting their sales or held carts."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("customers.write")
        now = timestamp()
        with self.repo.database.transaction():
            customer = self.repo.get("customers", customer_id)
            if not customer:
                raise NotFoundError("Customer was not found.")
            if int(customer["credit_minor"]) != 0:
                raise ValidationError("Settle the customer's store credit before deleting them.")
            self.repo.delete_customer(customer_id)
            self.repo.insert_outbox(
                "customers", customer["uuid"], "delete", {"id": customer_id}, now
            )
            user = self.auth.current_user if self.auth else None
            self.repo.insert("audit_log", {
                "user_id": user.id if user else None,
                "action": "delete",
                "entity": "customer",
                "entity_id": str(customer_id),
                "details_json": json.dumps({"uuid": customer["uuid"]}, sort_keys=True),
                "created_at": now,
            })

    def search(self, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        """Search customer names, phone numbers, and email addresses."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("customers.read")
        return self.repo.find("customers", search=query, search_fields=("name", "phone", "email"),
                              order_by="name", limit=limit)

    def get_with_history(self, customer_id: int) -> dict[str, Any]:
        """Return customer details and completed sales."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("customers.read")
        customer = self.repo.get("customers", customer_id)
        if not customer:
            raise NotFoundError("Customer was not found.")
        sales = self.repo.find("sales", {"customer_id": customer_id}, order_by="created_at", descending=True)
        return {"customer": customer, "sales": sales}

    def add_store_credit(self, customer_id: int, amount_minor: int) -> int:
        """Add a positive store-credit balance."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("customers.write")
        if amount_minor <= 0:
            raise ValidationError("Store credit must be positive.")
        customer = self.repo.get("customers", customer_id)
        if not customer:
            raise NotFoundError("Customer was not found.")
        balance = int(customer["credit_minor"]) + amount_minor
        now = timestamp()
        with self.repo.database.transaction():
            self.repo.update("customers", customer_id, {"credit_minor": balance})
            self.repo.insert_outbox(
                "customers", customer["uuid"], "update", {"credit_minor": balance}, now
            )
        return balance


class DiscountService:
    """Create and validate percentage or fixed-amount vouchers."""

    def __init__(self, repository: SqliteRepository, auth: AuthService | None = None) -> None:
        self.repo, self.auth = repository, auth

    def create_voucher(self, code: str, kind: str, value: int, **options: Any) -> int:
        """Create a voucher with optional validity, use, and minimum-spend limits."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("discounts.write")
        if kind not in {"percent", "fixed"} or value <= 0 or (kind == "percent" and value > 10_000):
            raise ValidationError("Voucher type or value is invalid.")
        return self.repo.insert("vouchers", {
            "code": code.strip().upper(), "kind": kind, "value": value,
            "starts_at": options.get("starts_at"), "expires_at": options.get("expires_at"),
            "max_uses": options.get("max_uses"), "minimum_minor": options.get("minimum_minor", 0),
        })

    def validate_voucher(self, code: str, subtotal_minor: int, now: datetime | None = None) -> dict[str, Any]:
        """Validate voucher availability and return its discount in minor units."""
        found = self.repo.find("vouchers", {"code": code.strip().upper(), "active": 1}, limit=1)
        moment = now or utc_now()
        if not found:
            raise VoucherError("Voucher is invalid or inactive.")
        voucher = found[0]
        if voucher["starts_at"] and moment.isoformat() < voucher["starts_at"]:
            raise VoucherError("Voucher is not valid yet.")
        if voucher["expires_at"] and moment.isoformat() > voucher["expires_at"]:
            raise VoucherError("Voucher has expired.")
        if voucher["max_uses"] is not None and voucher["used_count"] >= voucher["max_uses"]:
            raise VoucherError("Voucher usage limit has been reached.")
        if subtotal_minor < voucher["minimum_minor"]:
            raise VoucherError("Sale does not meet the voucher minimum spend.")
        discount = (subtotal_minor * voucher["value"] + 5000) // 10_000 if voucher["kind"] == "percent" else voucher["value"]
        return {**voucher, "discount_minor": min(discount, subtotal_minor)}

    def list_vouchers(self) -> list[dict[str, Any]]:
        """List vouchers by code."""
        return self.repo.find("vouchers", order_by="code")

    def deactivate(self, voucher_id: int) -> None:
        """Disable a voucher without deleting its usage history."""
        if self.auth and self.auth.enforcement_enabled:
            self.auth.require_permission("discounts.write")
        self.repo.update("vouchers", voucher_id, {"active": 0})
