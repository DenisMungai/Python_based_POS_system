"""Filesystem paths for application data."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Locations used for persistent, local application data."""

    data_dir: Path

    @property
    def backups_dir(self) -> Path:
        """Return the directory for local database backups."""
        return self.data_dir / "backups"

    @property
    def receipts_dir(self) -> Path:
        """Return the directory for generated receipts."""
        return self.data_dir / "receipts"

    @property
    def exports_dir(self) -> Path:
        """Return the directory for exported files."""
        return self.data_dir / "exports"

    @property
    def logs_dir(self) -> Path:
        """Return the directory for application logs."""
        return self.data_dir / "logs"

    @property
    def assets_dir(self) -> Path:
        """Return the directory for user-provided assets."""
        return self.data_dir / "assets"

    def create(self) -> None:
        """Create the local data directory structure."""
        for directory in (
            self.data_dir,
            self.backups_dir,
            self.receipts_dir,
            self.exports_dir,
            self.logs_dir,
            self.assets_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def get_app_paths(root_dir: Path | None = None) -> AppPaths:
    """Return app paths rooted at the project or a supplied directory."""
    project_dir = root_dir if root_dir is not None else Path(__file__).resolve().parents[2]
    return AppPaths(data_dir=project_dir / "data")
