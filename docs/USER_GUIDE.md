# POS User Guide

## First start

1. Enter the business name and preset.
2. Set the three-letter currency code.
3. Create the administrator account.
4. Choose whether to seed sample data.
5. Sign in and complete the required password change.

## Core workflow

- Use **Dashboard** for today's sales, orders, customers, average order, low stock, and the live checkout workspace.
- Use the configured sales label to open the dedicated catalogue and ticket workspace.
- Select **Hold sale** to save a ticket without changing stock. Open **Orders** to review held tickets and recall one into checkout.
- Press **F2** or **Ctrl+K** to focus catalogue search.
- Press **Enter** after typing a barcode to add the matching item.
- Use **Take payment**, then **Ctrl+Enter** to complete a checkout.
- After payment commits, watch the saved receipt generate, then review it or
  choose **Save text**, **Save PDF**, or **Print receipt** to save a local copy
  or send it to a local printer.
- M-Pesa is recorded as an offline payment after confirmation on the phone.
  The application does not initiate a network-based STK push.

## Operations

- **Products**: add, edit, archive, categorize, search, adjust stock, and
  attach local product images. Images appear on the sale catalogue cards.
  For the best fit, use 4:5 portrait photos (for example 1200x1500) with the
  subject centred and some margin, so the cover crop trims background only.
  Export the active catalogue to CSV or preview a CSV before importing it.
- **Customers**: register and update customers, review their purchase history,
  add store credit, and import/export customer CSV files.
- **Sales history**: inspect saved sales and receipt previews; authorized users
  can void completed sales with a required audit reason.
- **Orders**: review and recall held sales.
- **Returns**: review return history, find a receipt, enter quantities, and
  choose restocking separately for each returned item.
- **Discounts**: create percentage or fixed vouchers and deactivate active
  vouchers.

## Administration

- **Reports**: view date-range, daily, weekly, or monthly totals; weekly reports
  cover Monday through Sunday for the week containing the selected date. Review
  sales series, top
  items, payment and item-type breakdowns, and stock valuation; export sales
  CSV for the selected period.
- **Users**: create staff accounts and activate or deactivate accounts.
- **Settings**: use Business profile for business identity, currency, accent, and
  tax; Checkout options for feature modules and payment methods (including
  Bank transfer); and Data & backups to create or restore a local backup.

CSV import validates the complete file first and displays row-level issues.
The import is all-or-nothing; correct invalid rows in the source file and retry.
Receipt PDFs and text files are written locally using the saved sale snapshots.

## Keyboard flow

- `F2` / `Ctrl+K`: focus catalogue search.
- `Enter`: submit catalogue barcode search.
- `Ctrl+Enter`: complete payment.
- `Esc`: close a dialog.

## Release screenshots

Run `python scripts/release_screenshots.py` to regenerate the first-run setup
capture and current dashboard, checkout, products, and receipt captures for
Retail Shop and Café / Restaurant in `docs/screenshots/release/`.
