import sys
from PyQt6.QtWidgets import QApplication, QDialog

from app.styles import load_stylesheet
from app.ui.main_window import MainWindow
from app.ui.password_dialog import PasswordSetupDialog, PasswordUnlockDialog
from app.core.storage import is_first_run, load_config, needs_migration, load_accounts
from app.core.auth import load_dek
from app.core.logger import log_event


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
                    # Check if migration is needed (plaintext accounts exist)
                    if needs_migration():
                        # Force password setup to migrate plaintext accounts
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.warning(
                            None,
                            "Security Update Required",
                            "Your accounts need to be re-encrypted. "
                            "Please set a password to secure your accounts.",
                        )
                        existing_accounts = load_accounts()
                        dlg = PasswordSetupDialog(initial_accounts=existing_accounts)
                        if dlg.exec() == QDialog.DialogCode.Accepted:
                            dek = dlg.dek
                            has_password = True
                        else:
                            sys.exit(0)
                    else:
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.critical(
                            None,
                            "Error",
                            "No encryption key found. Please reset the application.",
                        )
                        sys.exit(1)

    # Now we have the DEK, create and show the main window
    log_event("app_started", has_password=has_password)
    win = MainWindow(dek=dek, has_password=has_password)
    win.show()
    result = app.exec()
    log_event("app_closed")
    sys.exit(result)


if __name__ == "__main__":
    main()
