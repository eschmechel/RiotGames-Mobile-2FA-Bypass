import base64
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

from ..core.auth import validate_password, hash_password
from ..core.storage import save_config
from ..core.encryption import generate_dek, generate_salt, derive_kek, encrypt


class PasswordSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set up Riot 2FA")
        self.setFixedSize(400, 300)
        self.setModal(True)
        self.dek = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title = QLabel("Set up a password to protect your 2FA seeds")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Password input
        layout.addWidget(QLabel("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(
            "At least 8 characters, 1 number, 1 special character"
        )
        layout.addWidget(self.password_input)

        # Confirm password
        layout.addWidget(QLabel("Confirm Password:"))
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Re-enter password")
        layout.addWidget(self.confirm_input)

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

        # Initialize an empty accounts file
        from ..core.storage import save_accounts

        save_accounts([], self.dek)

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
        if not password:
            QMessageBox.warning(self, "Error", "Please enter your password")
            return

        # Load config to get salt, encrypted_dek, and auth_hash
        from ..core.storage import load_config

        config = load_config()
        if not config:
            QMessageBox.critical(self, "Error", "Configuration not found")
            return

        # Verify password
        from ..core.auth import verify_password

        is_valid, needs_rehash = verify_password(config["auth_hash"], password)
        if not is_valid:
            QMessageBox.warning(self, "Error", "Incorrect password")
            return

        # If needs rehash, we'll update the hash later (for now just continue)
        # Derive KEK and decrypt DEK
        from ..core.encryption import derive_kek, decrypt
        import base64

        salt = bytes.fromhex(config["salt"])
        encrypted_dek = base64.b64decode(config["encrypted_dek"])
        kek = derive_kek(password, salt)
        try:
            dek = decrypt(encrypted_dek, kek)
        except Exception:
            QMessageBox.critical(self, "Error", "Failed to decrypt encryption key")
            return

        # Store the DEK in memory for the session (we'll pass it to main)
        self.dek = dek

        # If rehash is needed, update the stored hash
        if needs_rehash:
            from ..core.auth import hash_password
            from ..core.storage import save_config

            new_hash = hash_password(password)
            config["auth_hash"] = new_hash
            save_config(config)

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
        if not password:
            QMessageBox.warning(self, "Error", "Please enter your password")
            return

        # Load config to get salt, encrypted_dek, and auth_hash
        from ..core.storage import load_config

        config = load_config()
        if not config:
            QMessageBox.critical(self, "Error", "Configuration not found")
            return

        # Verify password
        from ..core.auth import verify_password

        is_valid, needs_rehash = verify_password(config["auth_hash"], password)
        if not is_valid:
            QMessageBox.warning(self, "Error", "Incorrect password")
            return

        # If needs rehash, we'll update the hash later
        # Derive KEK and decrypt DEK
        from ..core.encryption import derive_kek, decrypt
        import base64

        salt = bytes.fromhex(config["salt"])
        encrypted_dek = base64.b64decode(config["encrypted_dek"])
        kek = derive_kek(password, salt)
        try:
            dek = decrypt(encrypted_dek, kek)
        except Exception:
            QMessageBox.critical(self, "Error", "Failed to decrypt encryption key")
            return

        # Store the DEK in memory for the session
        self.dek = dek

        # If rehash is needed, update the stored hash
        if needs_rehash:
            from ..core.auth import hash_password
            from ..core.storage import save_config

            new_hash = hash_password(password)
            config["auth_hash"] = new_hash
            save_config(config)

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

        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText("New password (8+ chars, 1 number, 1 special)")
        layout.addWidget(self.new_password)

        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setPlaceholderText("Confirm new password")
        layout.addWidget(self.confirm_password)

        self.remember_checkbox = QCheckBox("Remember me (store key in Windows Credential Manager)")
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

    def accept_reset(self):
        current_password = self.current_password.text()
        new_password = self.new_password.text()
        confirm = self.confirm_password.text()

        if not current_password or not new_password:
            QMessageBox.warning(self, "Error", "Please fill in all password fields")
            return

        if new_password != confirm:
            QMessageBox.warning(self, "Error", "New passwords do not match")
            return

        validation_error = validate_password(new_password)
        if validation_error:
            QMessageBox.warning(self, "Invalid Password", validation_error)
            return

        from ..core.storage import load_config
        config = load_config()
        if not config:
            QMessageBox.critical(self, "Error", "Configuration not found")
            return

        from ..core.auth import verify_password
        is_valid, _ = verify_password(config["auth_hash"], current_password)
        if not is_valid:
            QMessageBox.warning(self, "Error", "Current password is incorrect")
            return

        from ..core.encryption import derive_kek, decrypt, generate_salt, encrypt
        import base64

        old_salt = bytes.fromhex(config["salt"])
        old_encrypted_dek = base64.b64decode(config["encrypted_dek"])
        old_kek = derive_kek(current_password, old_salt)

        try:
            dek = decrypt(old_encrypted_dek, old_kek)
        except Exception:
            QMessageBox.critical(self, "Error", "Failed to decrypt encryption key")
            return

        new_salt = generate_salt()
        new_kek = derive_kek(new_password, new_salt)
        new_encrypted_dek = encrypt(dek, new_kek)

        from ..core.auth import hash_password
        new_auth_hash = hash_password(new_password)

        config["salt"] = new_salt.hex()
        config["encrypted_dek"] = base64.b64encode(new_encrypted_dek).decode('utf-8')
        config["auth_hash"] = new_auth_hash

        if self.remember_checkbox.isChecked():
            from ..core.auth import store_dek
            if not store_dek(dek):
                QMessageBox.critical(self, "Error", "Failed to store encryption key")
                return

        from ..core.storage import save_config
        save_config(config)

        self.dek = dek
        self.accept()
