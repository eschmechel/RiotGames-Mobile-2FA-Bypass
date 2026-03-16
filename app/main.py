import sys
import os
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QGuiApplication

from app.styles import load_stylesheet
from app.ui.main_window import MainWindow
from app.ui.password_dialog import PasswordSetupDialog, PasswordUnlockDialog
from app.core.storage import is_first_run, load_config
from app.core.auth import validate_password
from app.core.encryption import generate_dek, derive_kek, encrypt
from app.core.storage import save_config, save_accounts, load_dek, store_dek, clear_dek


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())

    dek = None
    has_password = False

    # Check if it's the first run
    if is_first_run():
        # First run: show setup dialog
        dlg = PasswordSetupDialog()
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dek = dlg.dek
            has_password = True
        else:
            # User canceled setup, exit
            sys.exit(0)
    else:
        # Not first run: try to unlock
        config = load_config()
        if not config:
            # This should not happen, but if it does, treat as first run
            dlg = PasswordSetupDialog()
            if dlg.exec() == QDialog.DialogCode.Accepted:
                dek = dlg.dek
                has_password = True
            else:
                # User canceled setup, exit
                sys.exit(0)
        else:
            # We have a config
            if config.get("has_password", False):
                # Password is set, ask for it
                has_password = True
                dlg = PasswordUnlockDialog()
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    dek = dlg.dek
                else:
                    # User canceled, exit
                    sys.exit(0)
            else:
                # No password set, try to get DEK from keyring (for auto-unlock)
                dek = load_dek()
                if dek is None:
                    # No DEK in keyring, we need to create one?
                    # This should not happen if we have a config with has_password=False.
                    # But if it does, we treat as first run?
                    # Let's show a message and exit.
                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.critical(
                        None,
                        "Error",
                        "No encryption key found. Please reset the application.",
                    )
                    sys.exit(1)

    # Now we have the DEK, create and show the main window
    win = MainWindow(dek=dek, has_password=has_password)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
