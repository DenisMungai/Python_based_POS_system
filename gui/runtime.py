"""Set up first-run, authenticate, and launch the desktop shell."""

from backend.bootstrap import AppContext
from gui.app import create_application
from gui.dialogs.change_password import ChangePasswordDialog
from gui.dialogs.login import LoginDialog
from gui.dialogs.setup import SetupDialog
from gui.shell import AppWindow
from gui.styles.qss import build_stylesheet
from gui.styles.tokens import DEFAULT_PALETTE, PALETTES, Palette, px, set_active_palette


def run_desktop(context: AppContext) -> int:
    """Run setup/login flows and start the authenticated POS window."""
    application, bridge = create_application(context)
    try:
        if not context.setup.is_setup_complete():
            setup = SetupDialog(context)
            if setup.exec() != SetupDialog.DialogCode.Accepted:
                return 0
        palette_name = context.settings.get("accent_palette", DEFAULT_PALETTE.name) or DEFAULT_PALETTE.name
        palette: Palette = PALETTES.get(palette_name, DEFAULT_PALETTE)
        set_active_palette(palette)
        application.setStyleSheet(build_stylesheet(palette))
        if LoginDialog(context).exec() != LoginDialog.DialogCode.Accepted:
            return 0
        user = context.auth.current_user
        if user is not None and user.must_change_password:
            change_password = ChangePasswordDialog(context)
            if change_password.exec() != ChangePasswordDialog.DialogCode.Accepted:
                context.auth.logout()
                return 0
        window = AppWindow(context, bridge, palette)
        window.resize(px(1280), px(760))
        window.logout_requested.connect(application.quit)
        window.show()
        return application.exec()
    finally:
        bridge.unsubscribe()

