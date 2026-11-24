"""Reset a local staff password after a lockout or forgotten credential.

Usage (from the project root):

    python scripts/reset_admin_password.py
    python scripts/reset_admin_password.py --username manager

The new password is entered at a hidden prompt, so it is never written into
source code, shell history, or logs. This changes only the account credential
and lockout flags; sales, stock, customers, and all other data are preserved.
"""

import argparse
import getpass
import sqlite3
from pathlib import Path

from backend.core.config import get_app_paths
from backend.core.errors import PosError
from backend.core.security import PBKDF2_ITERATIONS, hash_password


def main() -> int:
    """Reset one local user's password and clear their temporary lockout."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--username", default="admin",
        help="staff username to reset (default: admin)",
    )
    parser.add_argument(
        "--root", type=Path, default=None,
        help="project root containing data/ (default: this project)",
    )
    arguments = parser.parse_args()

    database_path = get_app_paths(arguments.root).data_dir / "pos.db"
    if not database_path.is_file():
        raise SystemExit(
            f"Database not found at {database_path}. "
            "Start the application and complete setup first."
        )

    username = arguments.username.strip().lower()
    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match. Nothing was changed.")
    try:
        salt, digest = hash_password(password)
    except PosError as error:
        raise SystemExit(error.message) from error

    with sqlite3.connect(database_path, timeout=5.0) as connection:
        users = [
            str(row[0])
            for row in connection.execute("SELECT username FROM users ORDER BY username")
        ]
        if username not in users:
            raise SystemExit(
                f"No user named '{username}' exists. "
                f"Available users: {', '.join(users) or 'none'}"
            )
        connection.execute(
            """UPDATE users
                  SET salt = ?, password_hash = ?, hash_iterations = ?,
                      failed_logins = 0, locked_until = NULL,
                      must_change_password = 0, active = 1
                WHERE username = ?""",
            (salt, digest, PBKDF2_ITERATIONS, username),
        )

    print(f"Password reset for '{username}'. All sales, stock, and customers are intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
