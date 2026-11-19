"""Durable SQLite connection and transaction management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Generator, Any

from backend.core.errors import DatabaseError
from backend.core.migrations import run_migrations


class Database:
    """SQLite database configured for durable local transactions."""

    def __init__(
        self, path: Path | str = ":memory:", backup: Callable[[], object] | None = None
    ) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self.connection = sqlite3.connect(
                self.path,
                timeout=5.0,
                isolation_level=None,
                check_same_thread=False,
            )
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA foreign_keys=ON")
            self.connection.execute("PRAGMA busy_timeout=5000")
            run_migrations(self.connection, backup)
        except sqlite3.Error as error:
            raise DatabaseError("Could not initialize the local database.", reason=str(error)) from error
        self._transaction_depth = 0
        self._after_commit: list[Callable[[], Any]] = []

    def after_commit(self, callback: Callable[[], Any]) -> None:
        """Run a callback only after the outermost transaction commits."""
        if self._transaction_depth:
            self._after_commit.append(callback)
        else:
            callback()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Commit a business action atomically or roll it back on failure."""
        nested = self._transaction_depth > 0
        savepoint = f"pos_nested_{self._transaction_depth}"
        callback_count = len(self._after_commit)
        callbacks: list[Callable[[], Any]] = []
        try:
            if nested:
                self.connection.execute(f"SAVEPOINT {savepoint}")
            else:
                self.connection.execute("BEGIN IMMEDIATE")
            self._transaction_depth += 1
            yield self.connection
            self._transaction_depth -= 1
            if nested:
                self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            else:
                self.connection.commit()
                callbacks, self._after_commit = self._after_commit, []
        except Exception:
            del self._after_commit[callback_count:]
            if self._transaction_depth:
                self._transaction_depth -= 1
            if nested:
                self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            else:
                self.connection.rollback()
            raise
        for callback in callbacks:
            callback()

    def close(self) -> None:
        """Close the SQLite connection."""
        self.connection.close()
