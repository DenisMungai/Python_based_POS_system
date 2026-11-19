"""File-based application logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(logs_dir: Path) -> None:
    """Configure rotating logs without adding duplicate file handlers."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    log_path = (logs_dir / "pos.log").resolve()

    for handler in root_logger.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_path:
            return

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def close_logging(logs_dir: Path) -> None:
    """Close and remove the rotating file handler for the supplied data folder."""
    root_logger = logging.getLogger()
    log_path = (logs_dir / "pos.log").resolve()
    for handler in tuple(root_logger.handlers):
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_path:
            root_logger.removeHandler(handler)
            handler.close()
