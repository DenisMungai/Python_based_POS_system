# Inventory and Point-of-Sale Management System
## Lecturer Presentation Guide

This guide is a ready-to-deliver presentation for the Python Inventory and
Point-of-Sale Management System. It includes a suggested slide sequence,
speaker notes, a live demonstration, technical discussion, and likely
questions. Adjust the timing to fit the allocated session.

**Suggested duration:** 12–15 minutes, including a short live demonstration
and questions.

## Presentation at a glance

- **Project:** Inventory and Point-of-Sale Management System
- **Application type:** Offline-first desktop application
- **Interface:** Python with PySide6 Qt Widgets
- **Backend and persistence:** Python standard library and SQLite
- **Primary audience:** Small businesses that need local catalogue, inventory,
  customer, checkout, receipt, and reporting workflows
- **Presentation objective:** Explain the problem, system design, implemented
  workflows, data integrity approach, verification, and current boundaries

## Preparation checklist

Before presenting:

1. Launch the application and confirm it reaches the sign-in or main screen.
2. Use a presentation database with fictional business and customer data.
   Do not display the working `data/` directory or real business records.
3. Ensure the demo user has permission to access Products, Sales, Customers,
   Reports, and Settings.
4. Confirm the catalogue has at least one item with available stock and a
   configured payment method.
5. Test the demonstration steps once, including opening the saved receipt.
6. If a local printer is unavailable, demonstrate the on-screen receipt or
   save a local text/PDF receipt instead.
7. Keep the application offline during the presentation. M-Pesa is captured as
   a manually confirmed offline payment; the application does not initiate a
   payment gateway request.

The development and user workflow instructions are in [README.md](../README.md)
and [USER_GUIDE.md](USER_GUIDE.md). The detailed service contract is in
[INTEGRATION.md](../INTEGRATION.md).

## Slide-by-slide presentation

### Slide 1 — Title and introduction

**On the slide**

- Inventory and Point-of-Sale Management System
- Offline-first desktop software for small business operations
- Presenter, course, lecturer, and presentation date

**Speaker notes**

> Good [morning/afternoon]. My project is an Inventory and Point-of-Sale
> Management System. It is a desktop application intended to bring common
> small-business operations—catalogue management, stock tracking, customer
> records, sales, receipts, and reports—into one application that works
> locally without requiring an internet connection.

**Transition:** Introduce the business problem that motivated the system.

### Slide 2 — Problem statement

**On the slide**

- Stock counts and sales may be tracked in separate tools or manually.
- Re-entering prices and quantities can lead to inconsistencies.
- A completed sale should update stock and financial records together.
- Businesses need receipts and useful reports without depending on a cloud
  connection.

**Speaker notes**

> The core problem is operational fragmentation. When product information,
> stock levels, sales, and reporting are disconnected, staff may work from
> stale information and businesses can struggle to reconcile what was sold
> with what remains. This project addresses the workflow in one local system,
> with a particular focus on keeping the sale, payment record, receipt
> information, and stock movement consistent.

### Slide 3 — Aim and objectives

**On the slide**

**Aim:** Build a usable, service-backed desktop POS and inventory system for
small businesses.

**Objectives**

1. Provide configurable first-run business setup and staff authentication.
2. Manage catalogue items, categories, customers, and stock.
3. Support checkout, held sales, payments, receipts, returns, and voids.
4. Provide operational reports, CSV workflows, and local backups.
5. Keep business rules in testable backend services and store data locally.

**Speaker notes**

> The aim is not just to draw a checkout screen. The application connects
> visible controls to backend services that validate operations and persist
> their results. The objectives include both the day-to-day user workflow and
> the integrity and maintainability of the underlying system.

### Slide 4 — Users and scope

**On the slide**

- Designed for small shops and service-oriented businesses.
- Business setup supports presets such as Retail Shop, Café / Restaurant,
  Salon / Barber, and other listed business types.
- Configurable business name, currency, tax, accent palette, terminology, and
  payment methods.
- Main areas: Dashboard, Sales, Products, Customers, Orders, Sales history,
  Returns, Discounts, Reports, Users, and Settings.

**Speaker notes**

> The system is intended to adapt its business identity and terminology rather
> than present one fixed brand. For example, setup presets can change the
> terminology used for items and customers. The current desktop shell includes
> dedicated operational and administration areas, with routes shown according
> to permissions.

### Slide 5 — Main user workflow

**On the slide**

1. Configure the business and create an administrator.
2. Sign in and search or scan an item into the sale.
3. Review quantities, customer, discount, tax, and payment.
4. Commit the sale and show the saved receipt.
5. Review stock, sales history, and reports.

**Speaker notes**

> The workflow starts with first-run setup and authentication. During checkout,
> the cashier finds items through catalogue search or barcode lookup and adds
> them to the ticket. The service layer resolves the current price, tax, stock,
> and payment rules when processing the sale. After a successful commit, the
> application presents receipt details from the saved sale record.

**Transition:** Explain how the layers make this workflow reliable.

### Slide 6 — Architecture and technology

**On the slide**

```text
PySide6 GUI
    ↓
Backend services
    ↓
Repositories
    ↓
SQLite database
```

- GUI: Python and PySide6 Qt Widgets.
- Backend: Python standard library; no Qt dependency.
- Persistence: SQLite with migrations and explicit transactions.
- `AppContext` builds and shares the database, repository, event bus, and
  services.
- Backend events notify the GUI after successful commits.

**Speaker notes**

> The code follows a layered design. Views call services; services apply
> business rules and use repositories for persistence. The repository layer
> owns SQL. The backend does not import Qt, which keeps business behavior
> independently testable. A shared application context wires the components
> together at startup. When a business operation commits, events such as
> `sale_completed` or `stock_changed` allow relevant views to refresh.

### Slide 7 — Sale integrity and data handling

**On the slide**

- Money is stored as integer minor units.
- Quantities are stored as integer thousandths.
- A sale uses a database transaction.
- Sale item details are saved as snapshots.
- Stock changes are recorded in an append-only ledger.
- Invalid operations roll back rather than leave a partial sale.

**Speaker notes**

> Monetary calculations avoid binary floating-point storage: amounts use
> integer minor units and rounding uses decimal half-up behavior. Quantities
> support up to three decimal places by storing thousandths. When processing a
> sale, the service checks current stock and prices and commits the related
> sale records, payment records, receipt counter, stock movements, and audit
> information in one transaction. If a validation fails, the transaction is
> rolled back. Saved item snapshots preserve the name and price used at the
> time of sale even if the catalogue is edited later.

### Slide 8 — Features beyond checkout

**On the slide**

- Catalogue search, categories, barcode lookup, item images, and stock
  adjustments.
- Customer records, purchase history, and store credit.
- Held and recalled sales; vouchers; returns and authorized voids.
- Daily, monthly, and date-range reports, breakdowns, and CSV export.
- CSV import previews, local backups, and backup restoration.
- Local text/PDF receipts and local printer support.

**Speaker notes**

> Checkout is the central workflow, but the application also supports the
> surrounding operations. Staff can hold an unfinished sale without changing
> stock, recall it later, review previous sales, process returns, and manage
> vouchers. Administrators can review reports, manage users and settings, and
> create or restore local backups. CSV imports provide a preview and report
> invalid rows before data is applied.

### Slide 9 — Offline operation and security

**On the slide**

- Business data remains in local application storage.
- SQLite is configured for write-ahead logging, full synchronous durability,
  foreign keys, and a busy timeout.
- Passwords use salted PBKDF2-HMAC-SHA256 hashing.
- Failed-login lockout and service-level permission checks are implemented.
- No runtime network requests or telemetry.
- M-Pesa is manual offline tender recording, not an online integration.

**Speaker notes**

> Offline-first means the application’s normal workflows do not require a
> remote service. Local SQLite stores the business records and the application
> uses explicit durable transactions. Passwords are stored as salted hashes,
> not plaintext, and permission checks are enforced in backend services rather
> than relying only on hiding a screen. One important boundary is M-Pesa:
> staff record a payment that has been confirmed separately; this application
> does not connect to a payment gateway.

### Slide 10 — Verification and evidence

**On the slide**

- Automated tests use Python `unittest` and in-memory SQLite.
- Coverage includes money/tax conversions, migrations, password handling,
  stock updates and rollback, payments, vouchers, returns, permissions,
  reports, imports, and backups.
- GUI smoke, gallery, offline, and catalogue-scale scripts are available.
- Present only checks that have been run on the demonstration build.

**Speaker notes**

> Verification is organized around business behavior. For example, tests
> check that selling two units from stock ten leaves eight units and records
> the corresponding stock movement. Another test checks that overselling
> rejects the sale and rolls back changes. Other tests cover calculations,
> permissions, receipt numbering, returns, import validation, and backup
> restore. The repository also contains scripts for GUI smoke checks, offline
> checks, visual galleries, and a 5,000-item catalogue check.

> Before the presentation, I will state which commands were actually run for
> this build; the existence of a test or script is not itself evidence that it
> passed in this environment.

**Optional verification commands**

```powershell
python -m compileall backend gui scripts
python -m unittest discover -s backend\tests -v
python scripts\smoke.py
python scripts\offline_check.py
```

### Slide 11 — Current boundaries and future work

**On the slide**

- Runtime business data is local to the installation.
- There is no multi-device synchronization or remote backup service.
- M-Pesa is not a gateway integration.
- Printer compatibility should be confirmed on the target machine and printer.
- Continue release validation on a clean installation and intended hardware.

**Speaker notes**

> The current system deliberately prioritizes local, offline operation. As a
> result, it does not synchronize multiple devices or provide cloud backups,
> and it does not initiate online payments. Printing uses local operating
> system and printer facilities, so the intended printer should be tested on
> the actual deployment hardware. The project documentation tracks release
> gates; a feature should not be described as fully released until its
> relevant gate has been run and passed.

### Slide 12 — Conclusion

**On the slide**

- One local workflow for products, inventory, customers, sales, receipts, and
  reports.
- Layered Python architecture with service-owned business rules.
- Transactional SQLite persistence and testable offline operations.
- Thank you — questions?

**Speaker notes**

> To conclude, this project combines the key operational workflows of a small
> business in one desktop application. Its main technical strengths are the
> service-based separation of business logic, transactionally consistent
> sales, local-first data storage, and focused automated tests. Thank you. I’m
> happy to answer questions.

## Live demonstration script

**Suggested duration:** 3–5 minutes. Use prepared fictional data to avoid
spending the presentation on data entry.

1. **Orient the audience.** Point out the business name, signed-in user, and
   navigation. Mention that available routes depend on permissions.
2. **Show the dashboard.** Identify the daily KPIs and the current-sale
   workspace.
3. **Find an item.** Use catalogue search or a prepared barcode and add one
   product to the sale.
4. **Show the ticket.** Adjust quantity and explain that the GUI is collecting
   the requested sale; it is not the authority for final prices or totals.
5. **Take payment.** Use a configured method and complete the sale. Do not
   pretend to contact a payment provider.
6. **Show the receipt.** Point out the receipt number, saved item details,
   totals, and payment summary. Optionally demonstrate local save or print.
7. **Show the effect.** Navigate to Products or Sales history to show the
   updated stock or saved sale. If time permits, show a report or held sale.

**If something goes wrong**

- Do not retry a sale repeatedly without checking whether the previous attempt
  committed.
- Return to the ticket and explain that payment/stock validation occurs in the
  service layer.
- If live printing fails, use the on-screen receipt or a previously tested
  local text/PDF export.
- Keep a short screen recording or screenshots available as a fallback, while
  clearly identifying them as recorded evidence rather than a live run.

## Likely lecturer questions and suggested answers

### Why build a desktop application instead of a web application?

The project requirement prioritizes offline use and local data control. A
desktop application with SQLite can support day-to-day work without a network
service. This choice also avoids introducing a server or browser stack for the
current scope.

### Why use SQLite?

SQLite is included with Python, requires no separate database server, and is
well suited to a single-machine local application. The system uses migrations,
foreign keys, WAL mode, explicit transactions, and backups to support
consistent local persistence.

### How is overselling prevented?

The sale service re-reads current item prices and stock during checkout within
a database transaction. If stock is insufficient, it raises a business error
and the transaction rolls back. The GUI cannot override that service rule.

### How do you keep old receipts accurate after editing a product?

The sale stores item snapshots, including the item name and unit price at the
time of sale. Receipt rendering uses those saved transaction details rather
than the current catalogue record.

### Does the application process online payments?

No. It records configured tender methods and validates the payment details
required by the application. M-Pesa references are entered for a payment
confirmed outside the application. There are no gateway network calls.

### What happens if a sale fails part way through?

The related writes are grouped in a database transaction. An exception causes
the operation to roll back so that the sale, stock movement, and other related
records are not left partially committed.

### How are passwords protected?

The system hashes passwords with PBKDF2-HMAC-SHA256 using a per-user random
salt and at least 310,000 iterations. It also compares hashes in constant
time and locks an account temporarily after repeated failed logins.

### Can the system be used for different kinds of businesses?

Setup provides business presets and settings for terminology, currency, tax,
payment methods, modules, and accent palette. This supports adapting the
application to different business contexts. Some specialized workflows may
still require further development.

### What are the main limitations?

The current scope is local to one installation and does not provide
multi-device synchronization, cloud services, or online payment processing.
Printer behavior also needs validation on the target printer and operating
system.

### How was the system tested?

The repository includes focused `unittest` coverage for backend behaviors,
along with scripts for smoke, GUI, offline, and catalogue-scale checks. For
academic reporting, cite the actual commands and results observed on the
build being presented.

## Suggested closing statement

> This project demonstrates how a small-business POS can combine practical
> desktop workflows with a clear service architecture and transaction-safe
> local persistence. Its current boundaries are explicit, and the same
> separation makes it possible to extend the application while keeping
> calculations and permissions in the backend.

## Related project documentation

- [Project overview and setup](../README.md)
- [User workflow guide](USER_GUIDE.md)
- [Backend integration contract](../INTEGRATION.md)
- [Implementation decisions](DECISIONS.md)
- [Project scope and acceptance gates](../AGENTS.md)
