import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QIcon

from app.styles import load_stylesheet
from app.ui.main_window import MainWindow
from app.ui.password_dialog import PasswordSetupDialog, PasswordUnlockDialog
from app.core.storage import is_first_run, load_config, needs_migration, load_accounts
from app.core.auth import load_dek
from app.core.logger import log_event
from app.i18n import init as init_i18n


def main():
    app = QApplication(sys.argv)
    icon_path = Path(__file__).parent.parent / "assets" / "icon" / "riot2fa-bypass.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())

    init_i18n()

    dek = None
    has_password = False

    if is_first_run():
        dlg = PasswordSetupDialog()
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dek = dlg.dek
            has_password = True
        else:
            sys.exit(0)
    else:
        config = load_config()
        if not config:
            dlg = PasswordSetupDialog()
            if dlg.exec() == QDialog.DialogCode.Accepted:
                dek = dlg.dek
                has_password = True
            else:
                sys.exit(0)
        else:
            dek = load_dek()
            if dek is not None:
                has_password = config.get("has_password", False)
            elif config.get("has_password", False):
                has_password = True
                dlg = PasswordUnlockDialog()
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    dek = dlg.dek
                else:
                    sys.exit(0)
            else:
                if needs_migration():
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

    log_event("app_started", has_password=has_password)
    win = MainWindow(dek=dek, has_password=has_password)
    win.show()
    result = app.exec()
    log_event("app_closed")
    sys.exit(result)


if __name__ == "__main__":
    main()
