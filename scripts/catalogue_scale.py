"""Verify catalogue search remains practical at a 5,000-item scale."""

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.bootstrap import build_app_context


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pos-scale-") as directory:
        context = build_app_context(Path(directory))
        try:
            context.setup.complete_setup(
                "Scale Business", "Retail Shop", "KES", "admin", "Administrator",
                "scale-password",
            )
            context.auth.login("admin", "scale-password")
            started = time.perf_counter()
            for index in range(5000):
                context.catalog.create_item(
                    f"Scale item {index:04d}", 1000,
                    stock_milli=1000,
                    barcode=f"SCALE-{index:04d}",
                )
            created_seconds = time.perf_counter() - started
            started = time.perf_counter()
            results = context.catalog.search_items("Scale item 4999", limit=500)
            search_seconds = time.perf_counter() - started
            if len(results) != 1:
                raise RuntimeError(f"Expected 1 exact scale match, found {len(results)}.")
            if search_seconds > 1.0:
                raise RuntimeError(f"Catalogue search took {search_seconds:.3f}s.")
            print(
                f"5000-item catalogue passed: created in {created_seconds:.2f}s, "
                f"searched in {search_seconds:.3f}s."
            )
            return 0
        finally:
            context.close()


if __name__ == "__main__":
    raise SystemExit(main())
