# Changelog

## Unreleased

- Removed the em dash from the desktop window title between the business and
  sale labels.
- Aligned the administrator account controls with the sidebar navigation,
  added consistent account icons, and moved the welcome header down from the
  window chrome.
- Added weekly reports covering Monday through Sunday for the week containing
  the selected date; the calculated end date is shown and cannot be edited.
- Added an administrator self-service profile editor for username, display
  name, and optional password changes with current-password verification.
- Fixed Sales History table overflow at high DPI by shortening its displayed
  local timestamp and ensuring the action column fits its buttons.
- Completed clean-data setup/login and refreshed release screenshots for Retail
  Shop and Café / Restaurant; the 5,000-item catalogue check passed.
- Verified a clean virtual-environment dependency install and high-DPI GUI
  checkout smoke test; release acceptance remains open pending verification
  on the intended local receipt printer.
- Fixed catalogue cards to refresh after item, image, stock, and category
  changes and added an image preview while editing products.
- Reworked the sale catalogue into responsive 4:5 cover-cropped tiles with
  cached, EXIF-aware images, rounded image edges, and matching square checkout
  thumbnails.
- Removed stale catalogue cards and table actions immediately during refresh,
  preventing old widgets from painting over current rows or search results.
- Improved operational page headings and table action-row spacing to prevent
  clipped controls, and clarified the Returns empty-state layout.
- Reworked on-screen and printed receipts into itemized thermal layouts with
  saved totals, payment methods, and change; added local text/PDF export and
  refined receipt reveal sizing.
- Kept M-Pesa as manual offline tender capture. STK push remains excluded
  because it requires runtime gateway networking.
- Refreshed shared GUI surfaces, dropdowns, scrollbars, tables, tabs, and
  checkout actions with the supplied navy, emerald, teal, amber, and red palette.
- Added an animated saved-receipt reveal and local 80 mm receipt printing after
  checkout.
- Reorganized Settings into scrollable Business profile, Checkout options, and
  Data & backups sections with consistent cards and a persistent save action.
- Matched the reference dashboard composition with live KPI cards above an
  embedded catalogue and ticket, and added an Orders screen for listing and
  recalling saved sales. Holding and recall remain service-backed and do not
  alter stock until checkout.
- Added date-range, daily, and monthly reports with sales-series charts,
  payment/item-type breakdowns, and selectable CSV export.
- Added customer purchase history and credit actions, customer/item CSV import
  previews and export, authorized sale voiding, return history with per-line
  restock choices, and voucher deactivation.
- Corrected the payment-method setting to match the configured Bank transfer
  method and aligned customer CSV import authorization with customer-write
  permissions.
- See `AGENTS.md` for phase gates and `README.md` for final verification
  commands.
- Added backup restore selection, route accessible names/tooltips, a 5,000-item
  catalogue scale check, generated widget-gallery screenshots, and a user guide.
- Added operational GUI routes for Customers, Sales history, Returns, Discounts,
  Reports, Users, and Settings with service-backed actions.
- Added a service-backed Products and Categories GUI route with item create/edit,
  archive confirmation, category creation, catalogue search, filtering, and
  signed stock adjustments.
- Added first-run business setup, staff login, dashboard, and a service-backed
  current-sale workspace with catalogue search, categories, barcode lookup,
  stock-validated quantities, payment, and saved-receipt preview.
- Updated the desktop entry point to launch the GUI and refined accent contrast
  for palette controls.
- Added a catalogue category-listing service method for the GUI filter.

## Unreleased

- Add the Phase 0 project scaffold, local data-directory initialization, and
  rotating file logging.
- Document the complete product scope, GUI reference, architecture, and
  phase-by-phase gates in `AGENTS.md`.
- Implement SQLite migrations and durable transactions, backend primitives,
  authentication, catalogue/inventory/customer/voucher/sales/return/report/
  receipt/backup/import services, business presets, bootstrap wiring, and
  headless/offline verification scripts.
