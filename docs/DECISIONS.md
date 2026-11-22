# Decisions

## GUI display scaling

- The bundled design scale remains 0.9, with shared pixel tokens compensated
  for the primary display's device-pixel ratio. The desktop shell opens at the
  correspondingly scaled 1280×760 design size instead of maximizing beyond
  screens that expose a smaller physical viewport to Qt.
- Catalogue cards reflow based on the visible scroll-area width to avoid
  horizontal clipping on scaled or narrower windows.

## Phase 0

- Runtime data is stored in a project-local `data/` directory to support
  offline use and keep business records out of version control.
- The scaffold uses only the Python standard library until the GUI phase;
  `requirements.txt` reserves the sole third-party dependency for PySide6.
- The supplied `juniperpos.zip` is a static, mock browser demo. It is the
  visual/interaction reference for the PySide6 desktop UI only. Its mock
  persistence, simulated checkout/printing, and fixed Juniper branding do not
  replace real services, real offline workflows, or configurable branding
  required by the product scope.

## Final GUI and release

- Emerald is the default accent, using `#15A046` for primary fills. Small text
  on light surfaces uses the darker `#116B35` companion for WCAG AA contrast.
- Operations and administration remain permission-gated through backend
  services; the Qt shell only hides routes for users without access.
- Backup restore is restricted to paths in the application's managed backup
  directory and verifies SQLite integrity before replacement.
- The 5,000-item scale check uses a real temporary SQLite database and a timed
  catalogue search, not synthetic widget-only data.
- M-Pesa remains an offline manual-payment method: record the confirmed
  transaction reference at checkout, but do not initiate an STK push or make
  gateway network calls. This preserves the project's offline-only runtime
  requirement.
- Widget-gallery and release screenshots use real service data, not bundled
  mock application data. The release screenshot script uses isolated temporary
  databases with the Retail Shop and Café / Restaurant presets.
- Phase 8/9 are not declared complete based only on screenshots or smoke tests;
  update release status only after the full GUI checklist, 5,000-item scale
  check, and required backend/offline gates have passed.
- Checkout receipts can be saved as UTF-8 text or locally rendered PDF. PDF
  output uses a same-directory temporary file and atomic replacement.
