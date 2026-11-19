"""Headless end-to-end sale and stock verification."""

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.bootstrap import build_app_context
from backend.seed.demo_data import seed_retail


def main() -> int:
    """Create a fresh context and sell two units of item 101."""
    with tempfile.TemporaryDirectory(prefix="pos-smoke-") as directory:
        app = build_app_context(Path(directory))
        try:
            app.setup.complete_setup(
                "Demo Business", "Retail Shop", "KES", "admin", "Administrator", "demo-password"
            )
            app.auth.login("admin", "demo-password")
            item_id = seed_retail(app.catalog)[0]
            item = app.repository.get("items", item_id)
            sale = app.sales.process_sale(
                [{"item_id": item_id, "quantity_milli": 2000}],
                [{"method": "Cash", "amount_minor": item["price_minor"] * 2}],
            )
            stock = app.repository.get("items", item_id)["stock_milli"]
            if item_id != 101 or stock != 8000:
                raise AssertionError(f"Expected item 101 stock 8000 milli; got {item_id} / {stock}")
            print(app.receipts.render_text(sale.id))
            print(f"Available stock: {stock // 1000}")
        finally:
            app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
