# Inventory and Point-of-Sale Management System

An offline-first Python desktop application for inventory, customer, and sales
management.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

On first launch, the desktop app guides you through business setup and staff
login. Runtime files and rotating logs are stored locally under `data/`; this
directory is intentionally excluded from version control.

The SQLite database is `data/pos.db` (SQLite may create `pos.db-wal` and
`pos.db-shm` while the application is open). Database records include the
catalogue, stock ledger, customers, sales, receipts' transaction snapshots,
settings, and staff accounts. Local backups, exports, receipts, logs, and
uploaded assets are kept in the corresponding `data/backups`, `data/exports`,
`data/receipts`, `data/logs`, and `data/assets` folders. No business data is
sent over the network.

## Backend checks

```powershell
python -m unittest discover -s backend\tests -v
python scripts\smoke.py
python scripts\offline_check.py
```

Before release, run the focused GUI and performance checks below along with
`python -m compileall backend gui scripts` and the full backend test suite.

See [INTEGRATION.md](INTEGRATION.md) for the service APIs, transaction
semantics, error types, and events.

## GUI checks

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python scripts\gallery.py
python scripts\gui_smoke.py
python scripts\release_screenshots.py
```

The GUI smoke script drives first-run setup, login, catalogue search, and a
keyboard-only checkout against temporary local data.
GUI dimensions compensate for the primary display's device-pixel ratio so the
design scale remains consistent on high-DPI Windows displays. The shell opens
at the scaled 1280×760 design size rather than maximizing past a display's
physical bounds.

The release screenshot script captures setup and the dashboard, checkout,
products, and generated receipt for Retail Shop and Café / Restaurant.
For catalogue-scale verification:

```powershell
python scripts\catalogue_scale.py
```

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for the desktop workflow.

## Project scope and interface

The complete product scope and phase-by-phase acceptance gates are in
[AGENTS.md](AGENTS.md). The supplied Juniper & Co. browser demo is the visual
reference for a PySide6 desktop interface; its mock data and simulated
transactions are not production behavior.
