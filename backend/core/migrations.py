"""Ordered SQLite schema migrations."""

import sqlite3
from collections.abc import Callable

from backend.core.errors import MigrationError

SCHEMA_VERSION = 3


def _create_schema(connection: sqlite3.Connection) -> None:
    schema = """
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, parent_id INTEGER REFERENCES categories(id),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', category_id INTEGER REFERENCES categories(id),
            item_type TEXT NOT NULL DEFAULT 'product', unit TEXT NOT NULL DEFAULT 'each',
            barcode TEXT UNIQUE, price_minor INTEGER NOT NULL, cost_minor INTEGER NOT NULL DEFAULT 0,
            tax_rate_id INTEGER, tax_inclusive INTEGER NOT NULL DEFAULT 0,
            stock_milli INTEGER NOT NULL DEFAULT 0, low_stock_milli INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_items_name ON items(name COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS item_components (
            item_id INTEGER NOT NULL REFERENCES items(id), component_id INTEGER NOT NULL REFERENCES items(id),
            quantity_milli INTEGER NOT NULL CHECK(quantity_milli > 0),
            PRIMARY KEY(item_id, component_id)
        );
        CREATE TABLE IF NOT EXISTS expiry_batches (
            id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id),
            batch_code TEXT NOT NULL DEFAULT '', expiry_date TEXT NOT NULL,
            quantity_milli INTEGER NOT NULL CHECK(quantity_milli >= 0),
            UNIQUE(item_id, batch_code, expiry_date)
        );
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', credit_minor INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL, role TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL,
            hash_iterations INTEGER NOT NULL, pin_salt TEXT NOT NULL DEFAULT '', pin_hash TEXT NOT NULL DEFAULT '',
            failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT, active INTEGER NOT NULL DEFAULT 1,
            must_change_password INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tax_rates (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, rate_basis_points INTEGER NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS terminology (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS modules (key TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
            value INTEGER NOT NULL, starts_at TEXT, expires_at TEXT, max_uses INTEGER,
            used_count INTEGER NOT NULL DEFAULT 0, minimum_minor INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS counters (counter_date TEXT PRIMARY KEY, next_number INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, receipt_number TEXT NOT NULL UNIQUE,
            customer_id INTEGER REFERENCES customers(id), status TEXT NOT NULL, subtotal_minor INTEGER NOT NULL,
            discount_minor INTEGER NOT NULL, tax_minor INTEGER NOT NULL, total_minor INTEGER NOT NULL,
            change_minor INTEGER NOT NULL DEFAULT 0, voucher_code TEXT, note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, created_by INTEGER REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
            item_id INTEGER REFERENCES items(id), name_snapshot TEXT NOT NULL, item_type TEXT NOT NULL,
            unit_price_minor INTEGER NOT NULL, cost_minor INTEGER NOT NULL, tax_rate_basis_points INTEGER NOT NULL,
            tax_inclusive INTEGER NOT NULL, quantity_milli INTEGER NOT NULL,
            line_subtotal_minor INTEGER NOT NULL, line_tax_minor INTEGER NOT NULL,
            line_total_minor INTEGER NOT NULL, returned_milli INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sale_payments (
            id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
            method TEXT NOT NULL, amount_minor INTEGER NOT NULL, reference TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id),
            quantity_delta_milli INTEGER NOT NULL, reason TEXT NOT NULL, reference TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, created_by INTEGER REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id, id);
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, return_number TEXT NOT NULL UNIQUE,
            sale_id INTEGER NOT NULL REFERENCES sales(id), total_minor INTEGER NOT NULL,
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, created_by INTEGER REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS return_items (
            id INTEGER PRIMARY KEY, return_id INTEGER NOT NULL REFERENCES returns(id),
            sale_item_id INTEGER NOT NULL REFERENCES sale_items(id), quantity_milli INTEGER NOT NULL,
            amount_minor INTEGER NOT NULL, restocked INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS held_sales (
            id INTEGER PRIMARY KEY, uuid TEXT NOT NULL UNIQUE, customer_id INTEGER REFERENCES customers(id),
            cart_json TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), action TEXT NOT NULL,
            entity TEXT NOT NULL, entity_id TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sync_outbox (
            id INTEGER PRIMARY KEY, entity TEXT NOT NULL, entity_uuid TEXT NOT NULL, op TEXT NOT NULL,
            payload_json TEXT NOT NULL, created_at TEXT NOT NULL, synced_at TEXT
        );
        """
    for statement in schema.split(";"):
        if statement.strip():
            connection.execute(statement)
    connection.execute(
        "INSERT INTO sqlite_sequence(name, seq) SELECT 'items', 100 "
        "WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name='items')"
    )
    connection.execute("UPDATE sqlite_sequence SET seq=MAX(seq,100) WHERE name='items'")
    row = connection.execute("SELECT COUNT(*) FROM schema_version").fetchone()
    if row[0] == 0:
        connection.execute("INSERT INTO schema_version(version) VALUES (1)")


def _migration_two(connection: sqlite3.Connection) -> None:
    """Add expiry batches and enforce the stock ledger's append-only contract."""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS expiry_batches ("
        "id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL REFERENCES items(id), "
        "batch_code TEXT NOT NULL DEFAULT '', expiry_date TEXT NOT NULL, "
        "quantity_milli INTEGER NOT NULL CHECK(quantity_milli>=0), "
        "UNIQUE(item_id,batch_code,expiry_date))"
    )
    connection.execute(
        "CREATE TRIGGER IF NOT EXISTS stock_movements_no_update "
        "BEFORE UPDATE ON stock_movements BEGIN "
        "SELECT RAISE(ABORT, 'stock movements are append-only'); END"
    )
    connection.execute(
        "CREATE TRIGGER IF NOT EXISTS stock_movements_no_delete "
        "BEFORE DELETE ON stock_movements BEGIN "
        "SELECT RAISE(ABORT, 'stock movements are append-only'); END"
    )


def _migration_three(connection: sqlite3.Connection) -> None:
    """Add the managed local product-image location."""
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(items)").fetchall()
    }
    if "image_path" not in columns:
        connection.execute("ALTER TABLE items ADD COLUMN image_path TEXT NOT NULL DEFAULT ''")


MIGRATIONS: tuple[Callable[[sqlite3.Connection], None], ...] = (
    _create_schema, _migration_two, _migration_three,
)


def run_migrations(connection: sqlite3.Connection, backup: Callable[[], object] | None = None) -> None:
    """Apply ordered migrations, recording each version transactionally."""
    try:
        row = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone()
        current = connection.execute("SELECT version FROM schema_version").fetchone()[0] if row else 0
        if current < len(MIGRATIONS) and backup is not None:
            backup()
        for index in range(current, len(MIGRATIONS)):
            connection.execute("BEGIN IMMEDIATE")
            try:
                MIGRATIONS[index](connection)
                connection.execute("UPDATE schema_version SET version=?", (index + 1,))
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    except sqlite3.Error as error:
        raise MigrationError("Database migration failed.", reason=str(error)) from error
