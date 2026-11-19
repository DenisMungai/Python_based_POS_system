"""Staff login dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from backend.bootstrap import AppContext
from backend.core.errors import PosError
from gui.i18n import t
from gui.styles.tokens import px


class LoginDialog(QDialog):
    """Authenticate a staff member before opening the application shell."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle(t("sign_in", "Sign in"))
        self.setModal(True)
        self.setMinimumSize(px(760), px(480))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)
        brand = QFrame()
        brand.setObjectName("loginBrand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(px(38), px(42), px(38), px(42))
        mark = QLabel("JP")
        mark.setObjectName("loginMark")
        mark.setFixedSize(px(52), px(52))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(mark)
        brand_name = QLabel(context.settings.get("business_name", "POS") or "POS")
        brand_name.setObjectName("loginBrandName")
        brand_name.setWordWrap(True)
        brand_layout.addWidget(brand_name)
        brand_layout.addStretch(1)
        brand_layout.addWidget(QLabel(t("offline_ready", "Offline-ready point of sale")))
        split.addWidget(brand, 5)

        form_panel = QWidget()
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(px(44), px(42), px(44), px(42))
        form_layout.setSpacing(px(14))
        form_layout.addStretch(1)
        title = QLabel(t("sign_in", "Sign in"))
        title.setObjectName("drawerTitle")
        form_layout.addWidget(title)
        subtitle = QLabel(t("sign_in_subtitle", "Enter your staff credentials to continue"))
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        form_layout.addWidget(subtitle)
        form = QFormLayout()
        form.setSpacing(px(10))
        self.username = QLineEdit()
        self.username.setPlaceholderText(t("username", "Username"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText(t("password", "Password"))
        form.addRow(t("username", "Username"), self.username)
        form.addRow(t("password", "Password"), self.password)
        form_layout.addLayout(form)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        form_layout.addWidget(self.error_label)
        self.submit = QPushButton(t("sign_in", "Sign in"))
        self.submit.setProperty("primary", True)
        self.submit.clicked.connect(self._login)
        self.password.returnPressed.connect(self._login)
        form_layout.addWidget(self.submit)
        form_layout.addStretch(1)
        split.addWidget(form_panel, 6)
        layout.addLayout(split)

    def _login(self) -> None:
        """Authenticate through the backend and show user-safe failures."""
        self.submit.setEnabled(False)
        try:
            self.context.auth.login(self.username.text(), self.password.text())
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            self.submit.setEnabled(True)
            return
        self.accept()

