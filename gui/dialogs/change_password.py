"""Required first-login password update."""

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from backend.bootstrap import AppContext
from backend.core.errors import PosError
from gui.i18n import t
from gui.styles.tokens import px


class ChangePasswordDialog(QDialog):
    """Replace a temporary password before staff can enter the application."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle(t("change_password", "Change your password"))
        self.setModal(True)
        self.setMinimumWidth(px(420))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(14))
        heading = QLabel(t("password_change_required", "Choose a new password to continue."))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)
        form = QFormLayout()
        form.setSpacing(px(10))
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("current_password", "Current password"), self.current_password)
        form.addRow(t("new_password", "New password"), self.new_password)
        form.addRow(t("confirm_password", "Confirm new password"), self.confirm_password)
        layout.addLayout(form)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.submit = QPushButton(t("save_password", "Save password"))
        self.submit.setProperty("primary", True)
        self.submit.clicked.connect(self._save)
        self.confirm_password.returnPressed.connect(self._save)
        layout.addWidget(self.submit)

    def _save(self) -> None:
        """Validate confirmation and update credentials through AuthService."""
        self.submit.setEnabled(False)
        if self.new_password.text() != self.confirm_password.text():
            self.error_label.setText(t("passwords_do_not_match", "The new passwords do not match."))
            self.error_label.show()
            self.submit.setEnabled(True)
            return
        try:
            self.context.auth.change_password(
                self.current_password.text(), self.new_password.text()
            )
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            self.submit.setEnabled(True)
            return
        self.accept()

