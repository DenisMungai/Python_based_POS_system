"""Exercise local setup and checkout while socket connections are blocked."""

import socket
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.bootstrap import build_app_context
from backend.seed.demo_data import seed_retail


def main() -> int:
    """Run a local sale with common outbound socket paths disabled."""
    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection

    def blocked_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"Unexpected network connection attempted: {_args!r} {_kwargs!r}")

    socket.socket.connect = blocked_connect  # type: ignore[method-assign]
    socket.create_connection = blocked_connect  # type: ignore[assignment]
    try:
        with tempfile.TemporaryDirectory(prefix="pos-offline-") as directory:
            app = build_app_context(Path(directory))
            try:
                app.setup.complete_setup("Offline", "Retail Shop", "KES", "admin", "Admin", "demo-password")
                app.auth.login("admin", "demo-password")
                item_id = seed_retail(app.catalog)[0]
                item = app.repository.get("items", item_id)
                app.sales.process_sale(
                    [{"item_id": item_id, "quantity_milli": 1000}],
                    [{"method": "Cash", "amount_minor": item["price_minor"]}],
                )
                print("Offline setup and checkout passed.")
            finally:
                app.close()
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create_connection
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
