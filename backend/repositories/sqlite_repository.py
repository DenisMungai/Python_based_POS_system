"""Parameterized SQLite persistence operations."""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from backend.core.db import Database
from backend.core.errors import DatabaseError, DuplicateError, NotFoundError

TABLE_COLUMNS: dict[str, set[str]] = {
    "settings": {"key", "value"},
    "categories": {"id", "name", "parent_id", "created_at"},
    "items": {"id", "uuid", "name", "description", "category_id", "item_type", "unit",
              "barcode", "price_minor", "cost_minor", "tax_rate_id", "tax_inclusive",
              "stock_milli", "low_stock_milli", "image_path", "archived", "created_at", "updated_at"},
    "item_components": {"item_id", "component_id", "quantity_milli"},
    "expiry_batches": {"id", "item_id", "batch_code", "expiry_date", "quantity_milli"},
    "customers": {"id", "uuid", "name", "phone", "email", "notes", "credit_minor", "created_at"},
    "users": {"id", "uuid", "username", "display_name", "role", "salt", "password_hash",
              "hash_iterations", "pin_salt", "pin_hash", "failed_logins", "locked_until",
              "active", "must_change_password", "created_at"},
    "tax_rates": {"id", "name", "rate_basis_points", "is_default", "active"},
    "payment_methods": {"id", "name", "active"},
    "terminology": {"key", "value"},
    "modules": {"key", "enabled"},
    "vouchers": {"id", "code", "kind", "value", "starts_at", "expires_at", "max_uses",
                 "used_count", "minimum_minor", "active"},
    "counters": {"counter_date", "next_number"},
    "sales": {"id", "uuid", "receipt_number", "customer_id", "status", "subtotal_minor",
              "discount_minor", "tax_minor", "total_minor", "change_minor", "voucher_code",
              "note", "created_at", "created_by"},
    "sale_items": {"id", "sale_id", "item_id", "name_snapshot", "item_type", "unit_price_minor",
                   "cost_minor", "tax_rate_basis_points", "tax_inclusive", "quantity_milli",
                   "line_subtotal_minor", "line_tax_minor", "line_total_minor", "returned_milli"},
    "sale_payments": {"id", "sale_id", "method", "amount_minor", "reference"},
    "stock_movements": {"id", "item_id", "quantity_delta_milli", "reason", "reference",
                        "created_at", "created_by"},
    "returns": {"id", "uuid", "return_number", "sale_id", "total_minor", "note", "created_at",
                "created_by"},
    "return_items": {"id", "return_id", "sale_item_id", "quantity_milli", "amount_minor", "restocked"},
    "held_sales": {"id", "uuid", "customer_id", "cart_json", "note", "created_at"},
    "audit_log": {"id", "user_id", "action", "entity", "entity_id", "details_json", "created_at"},
    "sync_outbox": {"id", "entity", "entity_uuid", "op", "payload_json", "created_at", "synced_at"},
}
PRIMARY_KEYS = {
    "settings": "key", "terminology": "key", "modules": "key",
    "counters": "counter_date", "item_components": "item_id",
}


class SqliteRepository:
    """Provide safe, allowlisted CRUD and domain queries for services."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def _table(self, table: str) -> set[str]:
        if table not in TABLE_COLUMNS:
            raise ValueError(f"Unknown repository table: {table}")
        return TABLE_COLUMNS[table]

    def insert(self, table: str, values: Mapping[str, Any]) -> int:
        """Insert one row using validated columns and bound values."""
        columns = self._table(table)
        if not values or set(values) - columns:
            raise ValueError("Invalid insert columns.")
        names = tuple(values)
        sql = f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})"
        try:
            cursor = self.database.connection.execute(sql, tuple(values[name] for name in names))
            return int(cursor.lastrowid or 0)
        except sqlite3.IntegrityError as error:
            raise DuplicateError("A record with the same unique value already exists.") from error
        except sqlite3.Error as error:
            raise DatabaseError("Could not save the record.", reason=str(error)) from error

    def update(self, table: str, key: Any, values: Mapping[str, Any]) -> None:
        """Update a row selected by its primary key."""
        columns = self._table(table)
        if not values or set(values) - columns:
            raise ValueError("Invalid update columns.")
        key_name = PRIMARY_KEYS.get(table, "id")
        names = tuple(values)
        sql = f"UPDATE {table} SET {', '.join(f'{name}=?' for name in names)} WHERE {key_name}=?"
        try:
            cursor = self.database.connection.execute(sql, (*[values[name] for name in names], key))
            if cursor.rowcount == 0:
                raise NotFoundError(f"{table[:-1].capitalize()} was not found.")
        except sqlite3.IntegrityError as error:
            raise DuplicateError("A record with the same unique value already exists.") from error
        except sqlite3.Error as error:
            raise DatabaseError("Could not update the record.", reason=str(error)) from error

    def get(self, table: str, key: Any) -> dict[str, Any] | None:
        """Get a row by primary key."""
        self._table(table)
        key_name = PRIMARY_KEYS.get(table, "id")
        row = self.database.connection.execute(
            f"SELECT * FROM {table} WHERE {key_name}=?", (key,)
        ).fetchone()
        return dict(row) if row else None

    def find(
        self,
        table: str,
        filters: Mapping[str, Any] | None = None,
        search: str | None = None,
        search_fields: Sequence[str] = (),
        order_by: str | None = None,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Find rows with equality filters and optional literal substring search."""
        columns = self._table(table)
        filters = filters or {}
        if set(filters) - columns or any(field not in columns for field in search_fields):
            raise ValueError("Invalid query columns.")
        clauses: list[str] = []
        params: list[Any] = []
        for field, value in filters.items():
            if value is None:
                clauses.append(f"{field} IS NULL")
            else:
                clauses.append(f"{field}=?")
                params.append(value)
        if search and search_fields:
            clauses.append("(" + " OR ".join(f"{field} LIKE ? ESCAPE '\\'" for field in search_fields) + ")")
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.extend([f"%{escaped}%"] * len(search_fields))
        sql = f"SELECT * FROM {table}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if order_by:
            if order_by not in columns:
                raise ValueError("Invalid order column.")
            sql += f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}"
        if limit is not None:
            if limit < 0:
                raise ValueError("Limit cannot be negative.")
            sql += " LIMIT ?"
            params.append(limit)
        try:
            return [dict(row) for row in self.database.connection.execute(sql, params).fetchall()]
        except sqlite3.Error as error:
            raise DatabaseError("Could not read records.", reason=str(error)) from error

    def delete(self, table: str, key: Any) -> None:
        """Delete a row by primary key (use only for non-historical records)."""
        self._table(table)
        key_name = PRIMARY_KEYS.get(table, "id")
        self.database.connection.execute(f"DELETE FROM {table} WHERE {key_name}=?", (key,))

    def insert_outbox(self, entity: str, entity_uuid: str, operation: str, payload: Mapping[str, Any], created_at: str) -> None:
        """Append a sync-ready record; no network code consumes it."""
        self.insert("sync_outbox", {
            "entity": entity, "entity_uuid": entity_uuid, "op": operation,
            "payload_json": json.dumps(payload, sort_keys=True), "created_at": created_at,
        })

    def next_number(self, date_key: str, prefix: str) -> str:
        """Allocate a gap-free daily receipt or return number inside a transaction."""
        counter_key = f"{prefix}-{date_key}"
        row = self.get("counters", counter_key)
        number = int(row["next_number"]) if row else 1
        if row:
            self.update("counters", counter_key, {"next_number": number + 1})
        else:
            self.insert("counters", {"counter_date": counter_key, "next_number": 2})
        return f"{prefix}-{date_key}-{number:04d}"

    def stock_update(self, item_id: int, delta_milli: int, updated_at: str) -> bool:
        """Apply stock movement only when the resulting balance is nonnegative."""
        cursor = self.database.connection.execute(
            "UPDATE items SET stock_milli=stock_milli+?, updated_at=? WHERE id=? AND stock_milli+?>=0",
            (delta_milli, updated_at, item_id, delta_milli),
        )
        return cursor.rowcount == 1

    def daily_totals(self, start: str, end: str) -> dict[str, int]:
        """Aggregate completed sales within a UTC timestamp range."""
        row = self.database.connection.execute(
            "SELECT COUNT(*) AS order_count, COALESCE(SUM(total_minor),0) AS sales_minor "
            "FROM sales WHERE status='completed' AND created_at>=? AND created_at<?",
            (start, end),
        ).fetchone()
        return {"orders": int(row["order_count"]), "sales_minor": int(row["sales_minor"])}

    def top_items(self, start: str, end: str, limit: int = 10) -> list[dict[str, Any]]:
        """Aggregate sold quantities and amounts from immutable line snapshots."""
        rows = self.database.connection.execute(
            "SELECT si.item_id, si.name_snapshot AS name, SUM(si.quantity_milli) AS quantity_milli, "
            "SUM(si.line_total_minor) AS total_minor FROM sale_items si "
            "JOIN sales s ON s.id=si.sale_id WHERE s.status='completed' "
            "AND s.created_at>=? AND s.created_at<? GROUP BY si.item_id, si.name_snapshot "
            "ORDER BY total_minor DESC, name COLLATE NOCASE LIMIT ?",
            (start, end, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def sales_by_day(self, start: str, end: str) -> list[dict[str, Any]]:
        """Return completed-sale totals grouped by UTC calendar day."""
        rows = self.database.connection.execute(
            "SELECT substr(created_at,1,10) AS day, COUNT(*) AS orders, "
            "SUM(total_minor) AS sales_minor FROM sales WHERE status='completed' "
            "AND created_at>=? AND created_at<? GROUP BY substr(created_at,1,10) ORDER BY day",
            (start, end),
        ).fetchall()
        return [dict(row) for row in rows]

    def stock_valuation(self) -> dict[str, int]:
        """Return stock valuation based on cached quantities and unit cost."""
        row = self.database.connection.execute(
            "SELECT COALESCE(SUM(stock_milli*cost_minor),0) AS cost_milli_minor, "
            "COALESCE(SUM(stock_milli*price_minor),0) AS retail_milli_minor "
            "FROM items WHERE archived=0 AND item_type IN ('product','weighed','bundle')"
        ).fetchone()
        return {
            "cost_minor": (int(row["cost_milli_minor"]) + 500) // 1000,
            "retail_minor": (int(row["retail_milli_minor"]) + 500) // 1000,
        }

    def payment_breakdown(self, start: str, end: str) -> list[dict[str, Any]]:
        """Aggregate completed sale payments by method."""
        rows = self.database.connection.execute(
            "SELECT p.method, SUM(p.amount_minor) AS amount_minor FROM sale_payments p "
            "JOIN sales s ON s.id=p.sale_id WHERE s.status='completed' "
            "AND s.created_at>=? AND s.created_at<? GROUP BY p.method ORDER BY p.method",
            (start, end),
        ).fetchall()
        return [dict(row) for row in rows]

    def item_type_breakdown(self, start: str, end: str) -> list[dict[str, Any]]:
        """Aggregate completed sales by item type."""
        rows = self.database.connection.execute(
            "SELECT si.item_type, SUM(si.quantity_milli) AS quantity_milli, "
            "SUM(si.line_total_minor) AS total_minor FROM sale_items si "
            "JOIN sales s ON s.id=si.sale_id WHERE s.status='completed' "
            "AND s.created_at>=? AND s.created_at<? GROUP BY si.item_type ORDER BY si.item_type",
            (start, end),
        ).fetchall()
        return [dict(row) for row in rows]

    def replace_bundle_components(self, item_id: int, components: Sequence[tuple[int, int]]) -> None:
        """Replace component rows for one bundle inside the caller's transaction."""
        self.database.connection.execute("DELETE FROM item_components WHERE item_id=?", (item_id,))
        self.database.connection.executemany(
            "INSERT INTO item_components(item_id,component_id,quantity_milli) VALUES(?,?,?)",
            ((item_id, component_id, quantity_milli) for component_id, quantity_milli in components),
        )

    def expiring_batches(self, through_date: str) -> list[dict[str, Any]]:
        """List positive-stock batches expiring on or before a date."""
        rows = self.database.connection.execute(
            "SELECT b.*, i.name AS item_name FROM expiry_batches b "
            "JOIN items i ON i.id=b.item_id WHERE b.quantity_milli>0 AND b.expiry_date<=? "
            "AND i.archived=0 ORDER BY b.expiry_date, i.name",
            (through_date,),
        ).fetchall()
        return [dict(row) for row in rows]

    def restocked_return_quantity(self, sale_id: int, item_id: int) -> int:
        """Sum already-restocked returned units for one sold catalogue item."""
        row = self.database.connection.execute(
            "SELECT COALESCE(SUM(ri.quantity_milli),0) AS quantity FROM return_items ri "
            "JOIN returns r ON r.id=ri.return_id JOIN sale_items si ON si.id=ri.sale_item_id "
            "WHERE r.sale_id=? AND si.item_id=? AND ri.restocked=1",
            (sale_id, item_id),
        ).fetchone()
        return int(row["quantity"])

    def close(self) -> None:
        """Close the backing database."""
        self.database.close()
