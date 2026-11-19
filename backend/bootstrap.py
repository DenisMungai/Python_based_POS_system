"""Application startup and local runtime initialization."""

from dataclasses import dataclass
from pathlib import Path

from backend.core.config import get_app_paths
from backend.core.logging_setup import configure_logging
from backend.core.logging_setup import close_logging
from backend.core.db import Database
from backend.core.events import EventBus
from backend.repositories.sqlite_repository import SqliteRepository
from backend.services.catalog import (
    AuthService, CatalogService, CustomerService, DiscountService, InventoryService,
    SettingsService,
)
from backend.services.sales import ReturnService, SalesService
from backend.services.support import BackupService, ImportExportService, ReceiptService, ReportService, SetupService


@dataclass(frozen=True)
class AppContext:
    """Fully wired backend services and their shared infrastructure."""

    data_dir: Path
    database: Database
    repository: SqliteRepository
    events: EventBus
    settings: SettingsService
    auth: AuthService
    catalog: CatalogService
    inventory: InventoryService
    customers: CustomerService
    discounts: DiscountService
    sales: SalesService
    returns: ReturnService
    reports: ReportService
    receipts: ReceiptService
    backups: BackupService
    imports: ImportExportService
    setup: SetupService

    def close(self) -> None:
        """Close the app's local database connection."""
        self.database.close()
        close_logging(self.data_dir / "logs")


def initialize_app(root_dir: Path | None = None) -> AppContext:
    """Build the complete service context and initialize local files."""
    return build_app_context(root_dir)


def build_app_context(root_dir: Path | None = None) -> AppContext:
    """Create data folders, durable database, repositories, and services."""
    paths = get_app_paths(root_dir)
    paths.create()
    configure_logging(paths.logs_dir)
    database_path = paths.data_dir / "pos.db"
    if database_path.exists():
        backup_dir = paths.backups_dir

        def safety_backup() -> Path:
            backup_dir.mkdir(parents=True, exist_ok=True)
            destination = backup_dir / "pre-migration.db"
            import sqlite3
            target = sqlite3.connect(destination)
            try:
                source = sqlite3.connect(database_path)
                try:
                    source.backup(target)
                finally:
                    source.close()
            finally:
                target.close()
            return destination

        database = Database(database_path, safety_backup)
    else:
        database = Database(database_path)
    repository = SqliteRepository(database)
    events = EventBus()
    auth = AuthService(repository)
    settings = SettingsService(repository, events, auth)
    auth.enforcement_enabled = settings.get("setup_complete", "0") == "1"
    catalog = CatalogService(repository, events, auth, paths.assets_dir)
    inventory = InventoryService(repository, events, auth)
    customers = CustomerService(repository, auth)
    discounts = DiscountService(repository, auth)
    sales = SalesService(repository, events, auth)
    returns = ReturnService(repository, events, auth)
    reports = ReportService(repository, auth)
    receipts = ReceiptService(repository, settings)
    backups = BackupService(repository, paths.backups_dir, auth)
    imports = ImportExportService(repository, catalog, customers, auth)
    setup = SetupService(repository, settings, auth, catalog)
    return AppContext(
        paths.data_dir, database, repository, events, settings, auth, catalog,
        inventory, customers, discounts, sales, returns, reports, receipts,
        backups, imports, setup,
    )
