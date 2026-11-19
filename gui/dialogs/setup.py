"""First-run business and administrator configuration."""

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)

from backend.bootstrap import AppContext
from backend.core.errors import PosError
from gui.i18n import t
from gui.styles.tokens import px


class SetupDialog(QDialog):
    """Collect initial business details and create the administrator account."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle(t("first_run_setup", "Set up your business"))
        self.setModal(True)
        self.setMinimumWidth(px(520))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(24))
        layout.setSpacing(px(16))
        title = QLabel(t("welcome", "Welcome to your POS"))
        title.setObjectName("drawerTitle")
        layout.addWidget(title)
        subtitle = QLabel(t("setup_intro", "Add your business details and administrator account to get started."))
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setSpacing(px(10))
        self.business_name = QLineEdit()
        self.business_name.setPlaceholderText(t("business_name", "Business name"))
        self.business_type = QComboBox()
        self.business_type.addItems(context.setup.list_presets())
        self.currency = QLineEdit()
        self.currency.setMaxLength(3)
        self.currency.setPlaceholderText(t("currency_code", "Currency code"))
        self.admin_name = QLineEdit()
        self.admin_name.setPlaceholderText(t("your_name", "Your name"))
        self.username = QLineEdit()
        self.username.setPlaceholderText(t("username", "Username"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText(t("password", "Password"))
        form.addRow(t("business_name", "Business name"), self.business_name)
        form.addRow(t("business_type", "Business type"), self.business_type)
        form.addRow(t("currency", "Currency"), self.currency)
        form.addRow(t("administrator_name", "Administrator name"), self.admin_name)
        form.addRow(t("username", "Username"), self.username)
        form.addRow(t("password", "Password"), self.password)
        layout.addLayout(form)

        self.sample_data = QCheckBox(t("sample_data", "Add sample products and customers"))
        layout.addWidget(self.sample_data)
        self.error_label = QLabel()
        self.error_label.setObjectName("errorMessage")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.create_button = QPushButton(t("finish_setup", "Create business"))
        self.create_button.setProperty("primary", True)
        self.create_button.clicked.connect(self._complete)
        actions.addWidget(self.create_button)
        layout.addLayout(actions)
        self.password.returnPressed.connect(self._complete)

    def _complete(self) -> None:
        """Persist setup through the setup service and surface safe errors."""
        self.create_button.setEnabled(False)
        try:
            self.context.setup.complete_setup(
                self.business_name.text(), self.business_type.currentText(),
                self.currency.text(), self.username.text(), self.admin_name.text(),
                self.password.text(), sample_data=self.sample_data.isChecked(),
            )
        except PosError as error:
            self.error_label.setText(error.message)
            self.error_label.show()
            self.create_button.setEnabled(True)
            return
        self.accept()

