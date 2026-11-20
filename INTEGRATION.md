# Backend integration contract

The backend is standard-library-only and has no GUI dependency. Build one
shared service context with `backend.bootstrap.build_app_context(root_dir=None)`.
It creates the local data folders, configures SQLite durability and migrations,
and returns an `AppContext` containing the database, repository, event bus, and
services. Call `AppContext.close()` on shutdown. Pass `root_dir` in tests to
keep all runtime files isolated.

All monetary arguments and results are integer minor units. Quantities are
integer thousandths (`quantity_milli`). Timestamps persisted by services are
UTC ISO-8601 strings. SQL is restricted to `backend/repositories/` and
`backend/core/migrations.py`, and values are bound parameters.

Expected business errors derive from `PosError`: `ValidationError`,
`NotFoundError`, `DuplicateError`, `InsufficientStockError`,
`PermissionDeniedError`, `AuthenticationError`, `AccountLockedError`,
`VoucherError`, `PaymentError`, and `ImportErrorReport`. Persistence and
migration errors are `DatabaseError` and `MigrationError`.

## Context

| API | Arguments | Returns | Raises / events |
|---|---|---|---|
| `build_app_context(root_dir=None)` | Optional project data root | `AppContext` | `DatabaseError`, `MigrationError` |
| `AppContext.close()` | None | `None` | SQLite close errors |

`AppContext` exposes `database`, `repository`, `events`, `setup`, `settings`,
`auth`, `catalog`, `inventory`, `customers`, `discounts`, `sales`, `returns`,
`reports`, `receipts`, `backups`, and `imports`.

## Services

### SetupService

- `is_setup_complete()` -> `bool`.
- `list_presets()` -> `list[str]`.
- `apply_preset(name)` -> `None`; invalid names raise `ValidationError`.
- `complete_setup(business_name, business_type, currency, admin_username,
  admin_name, admin_password, sample_data=False)` -> administrator ID.
  Creates the profile, preset, admin, and optional preset sample catalogue in
  one transaction. Duplicate or invalid data raises the corresponding
  `PosError`.

### SettingsService

- `get(key, default=None)` -> optional string.
- `set(key, value)` -> `None`.
- `profile()`, `terminology()`, `modules()` -> dictionaries.
- `term(key, default=None)` -> string; missing key without a default raises
  `NotFoundError`.
- `set_terminology(values)`, `set_modules(values)` -> `None`.
- `set_tax_rate(name, rate_basis_points, is_default=False)` -> tax-rate ID.
- `tax_rates()` -> active tax-rate rows.
- `set_payment_methods(methods)` -> `None`.
- `payment_methods()` -> active payment-method rows.

Mutations emit `settings_changed` or `terminology_changed` only after commit.

### AuthService

- `create_user(username, display_name, role, password, pin=None)` -> user ID.
- `login(username, password)` -> `UserContext`; five consecutive failures
  lock the account for five minutes.
- `logout()` -> `None`; `current_user` -> optional `UserContext`.
- `require_permission(permission, user=None)` -> `None`, else
  `PermissionDeniedError`.
- `verify_admin_pin(pin)` -> `bool`.
- `list_users()` -> public user rows with credential fields removed.
- `update_user(user_id, **fields)` -> `None`.
- `update_profile(current_password, username, display_name, new_password=None)`
  -> `None`; updates the signed-in administrator's own username and display
  name, and optionally changes the password. A current password is always
  required. Duplicate usernames raise `DuplicateError`; invalid names or
  passwords raise `ValidationError`; non-admin users are denied.
- `change_password(old_password, new_password)` -> `None`.

Passwords and PINs use salted PBKDF2-HMAC-SHA256 with at least 310,000 rounds.
`UserContext.must_change_password` is true on first login until the user changes
the initial password.

### CatalogService

- `create_category(name, parent_id=None)` -> category ID.
- `list_categories()` -> categories ordered by name; requires `catalog.read`.
- `create_item(name, price_minor, **fields)` -> item ID. Optional fields:
  `item_type`, `cost_minor`, `stock_milli`, `low_stock_milli`, `description`,
  `category_id`, `unit`, `barcode`, `tax_rate_id`, `tax_inclusive`.
- `update_item(item_id, **fields)`, `archive_item(item_id)` -> `None`.
- `set_item_image(item_id, source)` -> managed local image path; validates and
  copies the image, then emits `catalog_changed` after commit.
- `search_items(query="", category_id=None, limit=100)` -> item rows.
- `find_by_barcode(barcode)` -> item row.
- `set_bundle_components(bundle_id, components)` -> `None`; each component has
  `item_id` and `quantity_milli`; recursive bundles are rejected.

Duplicate and invalid data raise `DuplicateError` / `ValidationError`;
missing records raise `NotFoundError`. Item creation and changes are written
to the sync outbox.

### InventoryService

- `adjust_stock(item_id, quantity_delta_milli, reason, user_id=None)` ->
  resulting stock milli-units.
- `restock(item_id, quantity_milli, user_id=None)` -> resulting stock.
- `low_stock_items()` -> low-stock item rows.
- `add_expiry_batch(item_id, batch_code, expiry_date, quantity_milli)` ->
  batch ID.
- `expiring_items(days=30)` -> expiring batch rows.
- `stock_history(item_id)` -> ordered ledger rows.
- `rebuild_stock_from_ledger()` -> `None`.

Negative stock raises `InsufficientStockError`; non-stock item types and
invalid quantities raise `ValidationError`. Mutations append the stock ledger
and audit log. `stock_changed` and threshold-crossing `low_stock_alert` events
are emitted after commit.

### CustomerService

- `register(name, phone="", email="", notes="")` -> customer ID.
- `update(customer_id, **fields)` -> `None`; fields are `name`, `phone`,
  `email`, and `notes`.
- `delete(customer_id)` -> `None`; removes customer details, detaches retained
  sales and held carts, and writes audit/outbox records. Customers with
  outstanding store credit cannot be deleted.
- `search(query="", limit=100)` -> customer rows.
- `get_with_history(customer_id)` -> customer and sale rows.
- `add_store_credit(customer_id, amount_minor)` -> updated credit balance.

Unknown customer IDs raise `NotFoundError`; invalid data raises
`ValidationError`.

### DiscountService

- `create_voucher(code, kind, value, **options)` -> voucher ID. `kind` is
  `percent` (basis points) or `fixed` (minor units); options may include
  `starts_at`, `expires_at`, `max_uses`, and `minimum_minor`.
- `validate_voucher(code, subtotal_minor, now=None)` -> voucher row with
  `discount_minor`.
- `list_vouchers()` -> voucher rows.
- `deactivate(voucher_id)` -> `None`.

Invalid, expired, inactive, exhausted, or minimum-spend-ineligible vouchers
raise `VoucherError`.

### SalesService

- `quote_sale(lines, voucher_code=None, at=None)` -> current server-calculated
  lines, subtotal, tax, discount, and total without mutating state.
- `process_sale(lines, payments, customer_id=None, voucher_code=None, note="",
  user_id=None, at=None)` -> `SaleResult`. Each line requires `item_id` and
  either `quantity_milli` or `quantity`; each payment requires `method` and
  `amount_minor`, and M-Pesa also requires `reference`.
- `hold_sale(lines, customer_id=None, note="")` -> held-sale ID.
- `recall_held(held_id, remove=True)` -> held sale with decoded lines.
- `list_held(limit=100)` -> recent held sales with decoded item requests.
- `get_sale(sale_id)` -> sale with item snapshots and payment rows.
- `list_sales(limit=100)` -> recent sales.
- `void_sale(sale_id, reason, user_id=None)` -> `None`.

Checkout re-reads item prices and stock in one `BEGIN IMMEDIATE` transaction.
Voucher usage, immutable line snapshots, payment rows, receipt counters, stock
movements, audit data, and outbox changes commit or roll back together.
Insufficient stock and invalid payment raise `InsufficientStockError` and
`PaymentError`. After commit it emits `sale_completed`, `stock_changed`, and
threshold-crossing `low_stock_alert`.

### ReturnService

- `find_sale_by_receipt(receipt_number)` -> sale with item snapshots.
- `list_returns(limit=100)` -> recent return rows with their original receipt
  numbers; requires `sales.read`.
- `create_return(sale_id, items, restock=True, note="", user_id=None)` ->
  persisted return row. Each item requires `sale_item_id` and
  `quantity_milli`; an optional per-item `restock` boolean overrides the
  method-wide default.

Returns exceeding unreturned quantity raise `ValidationError`. Successful
returns append return, ledger, outbox, and audit records and emit
`stock_changed` when stock is restored.

### ReportService

- `dashboard_kpis(now=None)` -> sales, order, customer, and average-order
  values for the UTC day.
- `daily_report(day)` -> daily totals and payment breakdown.
- `monthly_report(year, month)` -> totals and daily series.
- `sales_series(start, end)` -> daily series.
- `range_report(start, end)` -> totals, daily series, payment breakdown, and
  item-type breakdown for an ISO date/timestamp range.
- `top_items(start, end, limit=10)` -> ranked item snapshots.
- `breakdowns(start, end)` -> payment-method and item-type totals.
- `stock_valuation()` -> cost and retail values.
- `export_sales_csv(start, end, path)` -> written path.

### ReceiptService

- `build_receipt(sale_id)` -> business profile, saved sale, item snapshots,
  payments, and customer.
- `render_text(sale_id, width=42)` -> receipt text.
- `export_text(sale_id, path, width=42)` -> atomically saved UTF-8 receipt
  path.

On-screen and text receipts include the saved item snapshots, subtotal,
discount, tax, total, payment methods, and change when applicable. Full payment
references are intentionally omitted.

Missing sales raise `NotFoundError`; too-narrow receipt widths raise
`ValidationError`.

### BackupService

- `create_backup()` -> local SQLite snapshot path.
- `list_backups()` -> newest-first local backup paths.
- `restore_backup(path)` -> `None`; validates managed path and SQLite integrity
  and creates a safety backup before replacement.

### ImportExportService

- `preview_items_csv(content)` -> valid row and row-error collections.
- `import_items_csv(content, dry_run=True)` -> preview or imported IDs.
- `export_items_csv(path)` -> written path.
- `preview_customers_csv(content)` -> valid row and row-error collections.
- `import_customers_csv(content, dry_run=True)` -> preview or imported IDs.
- `export_customers_csv(path)` -> written path.

Item imports require `catalog.write`; customer imports require
`customers.write`. Exports require the corresponding read permission.

Invalid headers raise `ValidationError`; invalid data raises
`ImportErrorReport` containing row numbers and messages. Dry runs do not write
records. Export files are atomically replaced.

## EventBus

- `subscribe(event_name, listener)` -> unsubscribe callable.
- `publish(event_name, **payload)` -> `None`.

Events used by services: `stock_changed`, `sale_completed`,
`low_stock_alert`, `settings_changed`, `terminology_changed`, and
`catalog_changed` (catalogue mutations and image updates; refreshes dependent
views after commit).

## Cart model

`backend.models.cart.Cart` stores only item IDs and integer-thousandth
quantities. `add(item_id, quantity_milli=1000)`, `set_quantity(item_id,
quantity_milli)`, `remove(item_id)`, `clear()`, `lines()`, and
`to_sale_lines()` manage cart intent; prices and stock are always resolved
again by `SalesService.process_sale`.
