"""Self-service administrator profile editor."""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.errors import PosError
from gui.i18n import t
from gui.styles.tokens import px


class ProfileDialog(QDialog):
    """Edit the signed-in administrator's name, username, and password."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        user = context.auth.current_user
        if user is None or user.role != "Admin":
            raise RuntimeError("The administrator profile editor requires an admin login.")

        self.setWindowTitle(t("my_profile", "My profile"))
        self.setModal(True)
        self.setMinimumWidth(px(460))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(14))

        heading = QLabel(t("edit_profile", "Edit your profile"))
        heading.setObjectName("drawerTitle")
        layout.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(px(10))
        self.username = QLineEdit(user.username)
        self.display_name = QLineEdit(user.display_name)
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText(
            t("leave_blank_to_keep_password", "Leave blank to keep your current password")
        )
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("username", "Username"), self.username)
        form.addRow(t("display_name", "Display name"), self.display_name)
        form.addRow(t("current_password", "Current password"), self.current_password)
        form.addRow(t("new_password", "New password"), self.new_password)
        form.addRow(t("confirm_password", "Confirm new password"), self.confirm_password)
        layout.addLayout(form)

        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.save = QPushButton(t("save_changes", "Save changes"))
        self.save.setProperty("primary", True)
        self.save.clicked.connect(self._save)
        self.confirm_password.returnPressed.connect(self._save)
        layout.addWidget(self.save)

    def _save(self) -> None:
        """Verify the current password and save the profile through AuthService."""
        new_password = self.new_password.text()
        confirmation = self.confirm_password.text()
        if new_password != confirmation:
            self.error_label.setText(t("passwords_do_not_match", "The new passwords do not match."))
            self.error_label.show()
            return
        try:
            self.context.auth.update_profile(
                self.current_password.text(),
                self.username.text(),
                self.display_name.text(),
                new_password or None,
            )
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            return
        self.accept()
