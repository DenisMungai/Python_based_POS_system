"""Launch the offline-first desktop application."""

from backend.bootstrap import initialize_app
from gui.runtime import run_desktop


def main() -> int:
    """Initialize local data and run setup, login, and the POS shell."""
    context = initialize_app()
    try:
        return run_desktop(context)
    finally:
        context.close()


if __name__ == "__main__":
    raise SystemExit(main())
