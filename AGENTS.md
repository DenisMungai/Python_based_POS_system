# Project Scope and Development Guide

This file defines the complete scope, architecture, sequence, and acceptance
criteria for the Python Inventory and Point-of-Sale Management System. Follow
it whenever changing this repository.

## 1. Product goal

Build a polished, all-purpose, offline-first desktop application for small
businesses: retail shops, supermarkets, pharmacies, hardware stores, boutiques,
cafés and restaurants, salons, garages, wholesalers, and service businesses.

The finished application lets a business configure its profile and terminology,
register products and services, manage inventory and customers, process sales,
print or save receipts, and review operational reports. It must remain useful
without an internet connection and must protect committed sales against process
crashes and power loss.

## 2. Supplied GUI reference

The user supplied `juniperpos.zip`, a static browser-based POS demonstration.
Use it as a **visual and interaction reference** for the desktop GUI:

- Teal navigation rail, compact brand mark, active navigation pill, and user
  area pinned at the bottom.
- Soft neutral canvas, rounded white cards, restrained borders and shadows,
  bundled Poppins typography, and teal primary actions.
- Dashboard KPI cards above a two-column workspace: current sale ticket beside
  searchable, category-filtered catalogue cards.
- Full-width operational pages for Sales, Products, Customers, Orders,
  Reports, Returns, Discounts, Users, and Settings.
- Focused checkout and receipt experiences, responsive layouts, and concise
  operational wording.

The archive is a **static demo**, not the application implementation. Its
mock data, visitor-only state, browser prompts, simulated payment and printing,
and static Juniper branding must not replace real backend services. Implement
the target using PySide6 Qt Widgets, connect controls to the service layer,
and use configurable business branding and terminology. All customer-visible
checkout, receipt, stock, and report values must come from backend services.
Never present a simulated payment as a real payment.

## 3. Required product capabilities

### Setup and adaptable businesses

- First-run setup wizard for business details, business type, currency and tax,
  administrator account, and sample-data or empty-start choice.
- Presets: Retail Shop, Supermarket, Pharmacy, Hardware, Fashion Boutique,
  Café / Restaurant, Salon / Barber, Auto Garage, Wholesale, Service Business,
  and Custom.
- A preset configures terminology, categories, units, module defaults, tax,
  payment methods, and optional sample data transactionally.
- All user-facing business nouns are resolved through the terminology service.
  A salon may show Services and Clients; a restaurant may show Menu and Guests.
- Feature-module flags control optional UI and behavior. Disabled modules must
  not break other workflows.
- Business name, logo, currency, tax, accent palette, receipt settings, and
  payment methods are configurable. Do not hard-code a business brand,
  industry vocabulary, or currency in views.

### Catalogue and inventory

- Register, update, archive, search, and barcode-lookup items; manage
  categories and units; support CSV import/export.
- Item types: product, service, weighed, bundle, and non-inventory.
- Support variants, barcodes, weighed quantities, expiry/batches, serial
  numbers, price tiers, and other optional modules when enabled.
- Provide stock adjustments, restocking, low-stock and optional expiry alerts,
  stock history, and stock valuation.
- The stock ledger is append-only. Cached stock can be rebuilt from it.
- Services and non-inventory items do not change stock; bundles reduce their
  component items.

### Customers, sales, and receipts

- Register and update customers; search, view purchase history, and manage
  store credit when enabled.
- Support a sales cart, held and recalled sales, vouchers, split payments,
  change due, and configured payment methods.
- Resolve prices and calculate discounts, taxes, and totals in services, never
  in the GUI.
- Process each sale atomically: verify stock, compute totals, validate voucher
  and payment rules, allocate a receipt number, save immutable sale-item
  snapshots, reduce tracked stock, append ledger movements, update dependent
  balances, audit, then commit before publishing events.
- Reject overselling and roll back every effect if any part of the sale fails.
- Build receipts from saved transaction snapshots; support on-screen, text,
  PDF, and local printing in the GUI layer.
- Return and void workflows enforce permissions, limits, and stock-restock
  rules, and record their audit/ledger effects.

### Reporting, administration, and files

- Dashboard KPIs, sales history, daily and monthly sales reports, sales
  series, top items, breakdowns, stock valuation, and CSV export.
- User management with Admin, Manager, and Cashier roles; enforce permissions
  in services, not only in the UI.
- Settings for profile, terminology, modules, tax, currency, payment methods,
  receipt, accent palette, backup/restore, and import/export.
- Local receipts, CSV files, backups, logs, configuration, and uploaded assets
  are handled safely with atomic writes and validation.

## 4. Technology and layering

- Python 3.11 or newer. Backend dependencies are Python standard library only.
- PySide6 Qt Widgets is the only third-party dependency and is used only in
  `gui/`. Do not use Tkinter, QML, a web stack, ORM, or additional packages.
- SQLite through `sqlite3`, WAL mode, parameterized SQL, and explicit
  transactions.
- Strict call direction:

  ```text
  GUI views -> services -> repositories -> SQLite
                  |                 ^
                  +-- EventBus -----+
  ```

- `backend/` must never import Qt or know that a GUI exists. Services are the
  source of business rules and calculations. Repositories own all SQL.
- Create the GUI's dependencies through a single `AppContext` returned by
  `build_app_context()`.
- All operations must work offline. No runtime network requests, telemetry,
  CDN assets, remote authentication, or update checks.

## 5. Data and security rules

- Money is integer minor units; do not use floats for money. Use shared
  conversion, formatting, and tax helpers with `ROUND_HALF_UP` behavior.
- Quantities are integer thousandths. Tax rates use basis points.
- Timestamps are ISO-8601 UTC text; localize only for display.
- Item IDs start at 101. The acceptance example is item 101, Laptop, price
  850000, stock 10; selling quantity 2 leaves stock 8 and records a -2 ledger
  movement.
- Receipt IDs use `RCP-YYYYMMDD-0001`, sequential per day, gap-free and unique.
  Returns use `RET-...`.
- Sales store name, unit price, cost, and tax snapshots so later catalogue
  edits cannot rewrite historical reports or receipts.
- Important entities (`items`, `customers`, `sales`, `returns`, `users`) have
  UUIDs. The schema includes a stable device ID and a transactionally written
  sync outbox for future compatibility; do not add sync/network behavior.
- Passwords use PBKDF2-HMAC-SHA256 with a random per-user salt and at least
  310,000 iterations; compare hashes in constant time.
- Lock accounts for five minutes after five failed logins. Sensitive
  operations may require an administrator PIN.
- Never log passwords, PINs, or full payment references. Never commit secrets,
  real customer information, or contents of `data/`.
- Validate and copy uploaded images using safe extensions, size limits, and
  generated UUID filenames.
- Translate database exceptions at repository boundaries. Use a typed
  `PosError` hierarchy with user-safe messages. Roll back transactions on any
  exception; never hide failures or show raw stack traces to users.
- SQLite connections set WAL, `synchronous=FULL`, foreign keys, and a
  5000 ms busy timeout. Before pending migrations, make a safety backup.
  Migrations are ordered and tracked; never edit an applied migration.

## 6. GUI design and accessibility

- Use the supplied Juniper demo as visual guidance while retaining the
  all-purpose configurable business identity.
- Poppins Regular, Medium, and SemiBold are the only UI font weights.
- Keep all tokens, palettes, `UI_SCALE = 0.9`, `px(value)`, and generated QSS
  in `gui/styles/`. Every UI pixel value, including font sizes, spacing,
  radii, icons, and fixed dimensions, must pass through `px()`.
- Base design uses a 232 px teal sidebar at 100% scale, soft neutral canvas,
  white cards, restrained borders, rounded corners, and an 8 px spacing grid.
  The accent is selectable among six curated palettes with WCAG AA contrast.
- Do not use default Qt styling, native message boxes, emoji icons,
  gradients, neon, glass effects, oversized hero text, heavy shadows, or
  uncoordinated visual styles.
- Every visible control must perform a real service-backed action. Do not show
  dead buttons, fake interactions, placeholders, TODOs, or lorem ipsum.
- Provide default, hover, pressed, focus, and disabled states; focus uses a
  visible 2 px accent ring. Add tooltips to icon-only controls, concise empty
  states, elided long text, styled confirmations, and bottom-right toasts.
- Minimum window size is 1280x760. Layouts must avoid clipped or overflowing
  content.
- Keyboard flow: Ctrl+K global search, F2 catalogue search, Enter for scanned
  or typed barcode, Ctrl+Enter payment, Esc closes dialogs/drawers. Maintain
  logical tab order.
- Receipt preview is thermal-style with dashed separators and 58 mm / 80 mm
  layouts. Printing is invoked only through local OS/printer facilities.

## 7. Repository organization

Keep the established project layout and add modules within the relevant layer:

```text
AGENTS.md
README.md
INTEGRATION.md
CHANGELOG.md
requirements.txt
main.py
backend/
  bootstrap.py
  core/          # configuration, DB, migrations, errors, money, security,
                 # events, barcodes, files, logging, recovery and devices
  models/
  repositories/
  services/
  seed/
  tests/
gui/
  app.py
  styles/
  widgets/
  views/
  dialogs/
  i18n.py
assets/
  fonts/
  icons/
docs/
  GUI_SPEC.md
  BACKEND_SPEC.md
  DECISIONS.md
  reference/
scripts/
data/             # local runtime data; git-ignored
```

`INTEGRATION.md` documents every service method's arguments, return values,
exceptions, and emitted events. Keep `README.md`, `CHANGELOG.md`, relevant
specifications, and `docs/DECISIONS.md` current as work proceeds.

## 8. Required services

Implement business rules in services and persistence in repositories. The
service contract includes:

- `SetupService`: setup status, presets, preset application, setup completion.
- `SettingsService`: profile, terminology, modules, tax, payment methods, and
  generic settings.
- `AuthService`: login/logout/current user, PIN checks, user CRUD, permissions.
- `CatalogService`: item CRUD/archive/search/barcode, categories, CSV support.
- `InventoryService`: adjust/restock, low-stock/expiry items, stock history,
  ledger rebuild.
- `CustomerService`: registration/update/search/history/store credit.
- `DiscountService`: create, validate, list, and deactivate vouchers.
- `SalesService`: process, hold/recall, retrieve/list, and void sales.
- `ReturnService`: receipt lookup and return processing.
- `ReportService`: dashboard KPIs, daily/monthly reports, series, top items,
  breakdowns, valuation, and CSV export.
- `ReceiptService`: build and render receipts.
- `BackupService`: create/list/restore backups.
- `ImportExportService`: item/customer CSV dry runs and row-level reports.

Publish `stock_changed`, `sale_completed`, `low_stock_alert`,
`settings_changed`, and `terminology_changed` through the event bus after
successful commits where applicable.

## 9. Build phases and gates

Follow this order. A failed gate blocks starting the next phase. Do not skip
backend phases to create a mock GUI.

### Phase 0 — Scaffold

Project layout, virtual environment guidance, PySide6-only requirements,
`.gitignore` (including `data/`), first-run data folders, logging.

**Gate:** compile succeeds and first startup creates required local folders.

### Phase 1 — Backend core

Money, errors, database and transaction manager, full schema/migrations,
security, event bus, safe files, barcode support, logging, recovery.

**Gate:** unit tests cover money/tax rounding, migrations, password handling,
and barcode encoding.

### Phase 2 — Models, repositories, and services

Build typed models, then repositories, then services in this order: Settings,
Auth, Catalog, Inventory, Customer, Discount, Sales and Cart, Return, Report,
Receipt, Backup, ImportExport.

**Gate:** required service tests pass, including stock rollback, pricing/tax,
payments, vouchers, receipt sequencing, returns, permissions, reports, imports,
presets, and SQL-injection-safe parameter handling.

### Phase 3 — Presets, seed data, and bootstrap

Add business presets, General Retail/Café/Salon sample data, and
`build_app_context()`.

**Gate:** headless smoke test creates a fresh database, seeds a preset, sells
two units of item 101, verifies stock 8, and prints a text receipt.

### Phase 4 — GUI foundation

Poppins loading, design tokens and scaling, palettes, QSS, icon loader,
terminology helper, event-bus bridge, and reusable widgets including navigation
items, KPI/product cards, category chips, cart lines, quantity steppers,
status pills, search, toast, drawers, receipt, payment, and module controls.

**Gate:** widget gallery renders all widget states with the specified font,
scale, and styling.

### Phase 5 — Hero flow

Setup wizard, login, application shell, dashboard, Current Sale and catalogue,
payment dialog, success state, receipt preview.

**Gate:** compare against the supplied POS visual reference; complete a
service-backed keyboard-only sale end-to-end.

### Phase 6 — Operations screens

Products and categories, Customers, Orders, Sales history and receipt panel,
Returns, Discounts.

**Gate:** every shown action calls a real service; empty states and permissions
work.

### Phase 7 — Administration and insights

Reports, charts and export, Users, Settings, backup/restore, import/export,
terminology and module controls.

**Gate:** settings immediately update UI terminology/modules and service-level
permissions hold.

### Phase 8 — Polish

Complete control states, toasts, confirmations, tooltips, shortcuts, tab order,
text eliding, contrast, performance, low-stock notices, and visual QA.

**Gate:** full GUI checklist passes; 5,000-item catalogue remains smooth with
lazy loading and cached thumbnails.

### Phase 9 — Documentation and release

Finish user/developer documentation and screenshots for setup, dashboard,
sales, products, and receipts, including at least two business presets.

**Gate:** fresh installation and launch reach the setup wizard; all backend,
smoke, offline, and GUI gates pass.

## 10. Tests and verification

Use `unittest` and in-memory SQLite. Add focused regression tests for changed
behavior. Required core behavior includes:

1. Selling two from stock ten leaves eight and writes a -2 movement.
2. Overselling raises `InsufficientStockError` and changes nothing.
3. Services/non-inventory skip stock, weighed items accept 1.250, bundles
   reduce components.
4. Tax inclusive/exclusive, multiple rates, rounding, and cart/saved totals
   agree.
5. Voucher percentage/fixed, expiry, usage limit, and minimum-spend rules.
6. Split payments, change, M-Pesa reference, and underpayment validation.
7. Receipt numbers are unique, sequential, and reset daily.
8. Partial/full returns, optional restock, and over-return protection.
9. Voids restore stock and write audit records.
10. Low-stock events fire once per threshold crossing.
11. Authentication, lockout, permissions, and PIN behavior.
12. Reports agree with source data and top-items order is correct.
13. CSV dry run, row-numbered errors, and duplicate barcode handling.
14. Backup/restore round-trip and old-schema migration.
15. Preset changes from Café to Salon update terminology/categories/modules.
16. SQL-injection strings remain plain data.

Before a phase is declared complete, run its focused tests and update directly
related documentation. Before final release run:

```powershell
python -m compileall backend gui
python -m unittest discover -s backend/tests -v
python scripts/smoke.py
python scripts/offline_check.py
```

Also verify that `backend/` imports neither PySide6 nor third-party packages.
GUI phases additionally use the widget gallery, offscreen screenshots, and
manual keyboard-flow checks.

## 11. Working rules

- Inspect relevant code/specs before each phase; make precise, scoped changes.
- Preserve existing user changes. Never revert unrelated work or generated
  user data.
- Prefer standard-library and existing project helpers; do not add dependencies.
- Add a regression test when fixing a bug. Do not weaken tests to get a pass.
- Do not edit an applied migration; add a new ordered migration.
- Do not delete sold items; archive them.
- Do not put SQL/business calculations in GUI code.
- Do not leave unused imports, commented-out code, visible placeholders, or
  unimplemented controls.
- Record necessary judgment calls and conflicts in `docs/DECISIONS.md`.
- Do not claim a phase or feature is done unless its gate has been run and
  passed. Report work completed, verification performed, gate status, and
  deferred scope accurately.
