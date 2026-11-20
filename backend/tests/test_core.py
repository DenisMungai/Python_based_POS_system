"""Focused tests for exact arithmetic, security primitives, barcodes, and schema."""

import unittest
from decimal import Decimal
import sqlite3
import tempfile
from pathlib import Path

from backend.core.barcode import encode_code128, encode_ean13
from backend.core.db import Database
from backend.core.errors import ValidationError
from backend.core.migrations import run_migrations
from backend.core.money import (
    apply_tax, extract_inclusive_tax, fmt_qty, from_minor, qty_to_milli, to_minor,
)
from backend.core.security import hash_password, hash_pin, verify_password


class CoreTests(unittest.TestCase):
    """Verify backend primitives and migration idempotency."""

    def test_money_tax_and_quantity_use_exact_integer_conversions(self) -> None:
        self.assertEqual(to_minor("1.005"), 101)
        self.assertEqual(from_minor(101), Decimal("1.01"))
        self.assertEqual(apply_tax(100, 1600), 16)
        self.assertEqual(extract_inclusive_tax(116, 1600), 16)
        self.assertEqual(qty_to_milli("1.250"), 1250)
        with self.assertRaises(ValidationError):
            qty_to_milli("1.0001")

    def test_quantity_formatting_removes_only_insignificant_decimal_zeros(self) -> None:
        self.assertEqual(fmt_qty(2000), "2")
        self.assertEqual(fmt_qty(1250), "1.25")
        self.assertEqual(fmt_qty(0), "0")

    def test_password_hash_is_salted_and_verified(self) -> None:
        first_salt, first_hash = hash_password("secure-password")
        second_salt, second_hash = hash_password("secure-password")
        self.assertNotEqual(first_salt, second_salt)
        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(verify_password("secure-password", first_salt, first_hash))
        self.assertFalse(verify_password("wrong-password", first_salt, first_hash))
        pin_salt, pin_hash = hash_pin("1234")
        self.assertTrue(verify_password("1234", pin_salt, pin_hash))

    def test_barcode_encoders_generate_expected_symbol_lengths(self) -> None:
        self.assertTrue(encode_code128("POS-101"))
        self.assertEqual(len(encode_ean13("4006381333931")), 95)
        with self.assertRaises(ValidationError):
            encode_ean13("4006381333932")

    def test_migrations_are_idempotent_and_start_item_ids_at_101(self) -> None:
        database = Database(":memory:")
        try:
            run_migrations(database.connection)
            item_id = database.connection.execute(
                "INSERT INTO items(uuid,name,price_minor,created_at,updated_at) VALUES('u','x',1,'t','t')"
            ).lastrowid
            self.assertEqual(item_id, 101)
            version = database.connection.execute("SELECT version FROM schema_version").fetchone()[0]
            self.assertEqual(version, 3)
        finally:
            database.close()

    def test_existing_version_one_database_gets_safety_backup_and_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.db"
            connection = sqlite3.connect(path)
            connection.executescript(
                "CREATE TABLE schema_version(version INTEGER NOT NULL);"
                "INSERT INTO schema_version VALUES(1);"
                "CREATE TABLE items(id INTEGER PRIMARY KEY);"
                "CREATE TABLE stock_movements(id INTEGER PRIMARY KEY);"
            )
            connection.close()
            backups: list[str] = []
            database = Database(path, lambda: backups.append("backup"))
            try:
                self.assertEqual(backups, ["backup"])
                self.assertEqual(
                    database.connection.execute("SELECT version FROM schema_version").fetchone()[0], 3
                )
            finally:
                database.close()

    def test_stock_ledger_rejects_update_and_delete(self) -> None:
        database = Database(":memory:")
        try:
            database.connection.execute(
                "INSERT INTO items(id,uuid,name,price_minor,created_at,updated_at) "
                "VALUES(101,'test','Item',100,'now','now')"
            )
            database.connection.execute(
                "INSERT INTO stock_movements(item_id,quantity_delta_milli,reason,created_at) "
                "VALUES(101,1000,'opening','now')"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                database.connection.execute("UPDATE stock_movements SET reason='rewritten' WHERE id=1")
            with self.assertRaises(sqlite3.IntegrityError):
                database.connection.execute("DELETE FROM stock_movements WHERE id=1")
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()
