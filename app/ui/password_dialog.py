import base64
import secrets
import string
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QMessageBox,
)

from ..core.auth import validate_password, hash_password, verify_password
from ..core.storage import save_config, load_config
from ..core.encryption import generate_dek, generate_salt, derive_kek, decrypt, encrypt


def _generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password meeting app requirements."""
    letters = string.ascii_letters
    digits = string.digits
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    all_chars = letters + digits + special

    password = [
        secrets.choice(letters),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    for _ in range(length - 3):
        password.append(secrets.choice(all_chars))

    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def _verify_password_and_get_dek(parent, password: str) -> tuple[bool, bytes | None]:
    """Shared helper to verify password and decrypt DEK. Returns (success, dek)."""
    if not password:
        QMessageBox.warning(parent, "Error", "Please enter your password")
        return False, None

    config = load_config()
    if not config:
        QMessageBox.critical(parent, "Error", "Configuration not found")
        return False, None

    is_valid, needs_rehash = verify_password(config["auth_hash"], password)
    if not is_valid:
        QMessageBox.warning(parent, "Error", "Incorrect password")
        return False, None

    salt = bytes.fromhex(config["salt"])
    encrypted_dek = base64.b64decode(config["encrypted_dek"])
    kek = derive_kek(password, salt)
    try:
        dek = decrypt(encrypted_dek, kek)
    except Exception:
        QMessageBox.critical(parent, "Error", "Failed to decrypt encryption key")
        return False, None

    if needs_rehash:
        new_hash = hash_password(password)
        config["auth_hash"] = new_hash
        save_config(config)

    return True, dek


class PasswordSetupDialog(QDialog):
    def __init__(self, parent=None, initial_accounts=None):
        super().__init__(parent)
        self.setWindowTitle("Set up Riot 2FA")
        self.setFixedSize(400, 300)
        self.setModal(True)
        self.dek = None
        self.initial_accounts = initial_accounts or []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title = QLabel("Set up a password to protect your 2FA seeds")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Password input
        layout.addWidget(QLabel("Password:"))
        password_layout = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(
            "At least 8 characters, 1 number, 1 special character"
        )
        password_layout.addWidget(self.password_input)
        generate_btn = QPushButton("Generate")
        generate_btn.setFixedWidth(80)
        generate_btn.clicked.connect(self._generate_password)
        password_layout.addWidget(generate_btn)
        layout.addLayout(password_layout)

        # Confirm password
        layout.addWidget(QLabel("Confirm Password:"))
        confirm_layout = QHBoxLayout()
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Re-enter password")
        confirm_layout.addWidget(self.confirm_input)
        confirm_layout.addWidget(QLabel(""))
        confirm_layout.addStretch()
        layout.addLayout(confirm_layout)

        # Show password checkbox
        self.show_password_checkbox = QCheckBox("Show password")
        self.show_password_checkbox.toggled.connect(self._toggle_password_visibility)
        layout.addWidget(self.show_password_checkbox)

        # Remember me checkbox
        self.remember_checkbox = QCheckBox(
            "Remember me (store key in Windows Credential Manager)"
        )
        layout.addWidget(self.remember_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.ok_button = QPushButton("Set Password")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept_setup)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _generate_password(self):
        password = _generate_secure_password()
        self.password_input.setText(password)
        self.confirm_input.setText(password)
        self.show_password_checkbox.setChecked(True)

    def _toggle_password_visibility(self, checked):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(mode)
        self.confirm_input.setEchoMode(mode)

    def accept_setup(self):
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if password != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return

        validation_error = validate_password(password)
        if validation_error:
            QMessageBox.warning(self, "Invalid Password", validation_error)
            return

        # Generate a random DEK for encrypting account data
        self.dek = generate_dek()
        # Generate a salt for the KEK
        salt = generate_salt()
        # Derive KEK from password and salt
        kek = derive_kek(password, salt)
        # Encrypt the DEK with KEK
        encrypted_dek = encrypt(self.dek, kek)
        # Hash the password for verification
        auth_hash = hash_password(password)

        # Save config
        config = {
            "version": 2,
            "has_password": True,
            "salt": salt.hex(),
            "encrypted_dek": base64.b64encode(encrypted_dek).decode("utf-8"),
            "auth_hash": auth_hash,
        }
        save_config(config)

        # If remember me is checked, store the DEK in keyring for auto-unlock
        if self.remember_checkbox.isChecked():
            from ..core.auth import store_dek

            if not store_dek(self.dek):
                QMessageBox.critical(self, "Error", "Failed to store encryption key")
                return

        # Initialize accounts file (migrate existing plaintext if any)
        from ..core.storage import save_accounts

        save_accounts(self.initial_accounts, self.dek)

        self.accept()


class PasswordUnlockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unlock Riot 2FA")
        self.setFixedSize(350, 200)
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Enter your password to unlock your 2FA seeds:"))

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")
        layout.addWidget(self.password_input)

        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.unlock_button = QPushButton("Unlock")
        self.unlock_button.setDefault(True)
        self.unlock_button.clicked.connect(self.accept_unlock)
        button_layout.addWidget(self.unlock_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def accept_unlock(self):
        password = self.password_input.text()
        success, dek = _verify_password_and_get_dek(self, password)
        if not success:
            return

        self.dek = dek
        self.accept()


class PasswordReauthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Re-authenticate")
        self.setFixedSize(350, 200)
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(
            QLabel("Please re-enter your password to view or copy the seed:")
        )

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")
        layout.addWidget(self.password_input)

        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.ok_button = QPushButton("Continue")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept_reauth)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def accept_reauth(self):
        password = self.password_input.text()
        success, dek = _verify_password_and_get_dek(self, password)
        if not success:
            return

        self.dek = dek
        self.accept()


class PasswordResetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reset Password")
        self.setFixedSize(400, 350)
        self.setModal(True)
        self.dek = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Enter your current password:"))

        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_password.setPlaceholderText("Current password")
        layout.addWidget(self.current_password)

        layout.addSpacing(12)

        layout.addWidget(QLabel("Enter new password:"))

        new_password_layout = QHBoxLayout()
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText(
            "New password (8+ chars, 1 number, 1 special)"
        )
        new_password_layout.addWidget(self.new_password)
        generate_btn = QPushButton("Generate")
        generate_btn.setFixedWidth(80)
        generate_btn.clicked.connect(self._generate_password)
        new_password_layout.addWidget(generate_btn)
        layout.addLayout(new_password_layout)

        confirm_layout = QHBoxLayout()
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setPlaceholderText("Confirm new password")
        confirm_layout.addWidget(self.confirm_password)
        confirm_layout.addWidget(QLabel(""))
        confirm_layout.addStretch()
        layout.addLayout(confirm_layout)

        self.show_password_checkbox = QCheckBox("Show password")
        self.show_password_checkbox.toggled.connect(self._toggle_password_visibility)
        layout.addWidget(self.show_password_checkbox)

        self.remember_checkbox = QCheckBox(
            "Remember me (store key in Windows Credential Manager)"
        )
        layout.addWidget(self.remember_checkbox)

        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.ok_button = QPushButton("Reset Password")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept_reset)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _generate_password(self):
        password = _generate_secure_password()
        self.new_password.setText(password)
        self.confirm_password.setText(password)
        self.show_password_checkbox.setChecked(True)

    def _toggle_password_visibility(self, checked):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.new_password.setEchoMode(mode)
        self.confirm_password.setEchoMode(mode)

    def _validate_inputs(
        self, current_password: str, new_password: str, confirm: str
    ) -> bool:
        """Validate password inputs.

        Returns:
            True if all inputs are valid, False otherwise (shows error dialog on failure).
        """
        if not current_password or not new_password:
            QMessageBox.warning(self, "Error", "Please fill in all password fields")
            return False

        if new_password != confirm:
            QMessageBox.warning(self, "Error", "New passwords do not match")
            return False

        validation_error = validate_password(new_password)
        if validation_error:
            QMessageBox.warning(self, "Invalid Password", validation_error)
            return False

        return True

    def _rotate_keys(
        self, current_password: str, new_password: str
    ) -> tuple[bool, bytes | None]:
        """Rotate encryption keys. Returns (success, dek)."""
        config = load_config()
        if not config:
            QMessageBox.critical(self, "Error", "Configuration not found")
            return False, None

        is_valid, _ = verify_password(config["auth_hash"], current_password)
        if not is_valid:
            QMessageBox.warning(self, "Error", "Current password is incorrect")
            return False, None

        old_salt = bytes.fromhex(config["salt"])
        old_encrypted_dek = base64.b64decode(config["encrypted_dek"])
        old_kek = derive_kek(current_password, old_salt)

        try:
            dek = decrypt(old_encrypted_dek, old_kek)
        except Exception:
            QMessageBox.critical(self, "Error", "Failed to decrypt encryption key")
            return False, None

        new_salt = generate_salt()
        new_kek = derive_kek(new_password, new_salt)
        new_encrypted_dek = encrypt(dek, new_kek)

        new_auth_hash = hash_password(new_password)

        config["salt"] = new_salt.hex()
        config["encrypted_dek"] = base64.b64encode(new_encrypted_dek).decode("utf-8")
        config["auth_hash"] = new_auth_hash

        if self.remember_checkbox.isChecked():
            from ..core.auth import store_dek

            if not store_dek(dek):
                QMessageBox.critical(self, "Error", "Failed to store encryption key")
                return False, None

        save_config(config)

        return True, dek

    def accept_reset(self):
        current_password = self.current_password.text()
        new_password = self.new_password.text()
        confirm = self.confirm_password.text()

        if not self._validate_inputs(current_password, new_password, confirm):
            return

        success, dek = self._rotate_keys(current_password, new_password)
        if not success:
            return

        self.dek = dek
        self.accept()
