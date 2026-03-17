import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QMessageBox,
    QDialog,
    QSystemTrayIcon,
    QMenu,
    QLineEdit,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon

from app.core import (
    load_accounts,
    save_accounts,
    PERIOD,
    get_minimize_to_tray,
    set_minimize_to_tray,
    get_auto_start,
    set_auto_start,
    get_notifications_enabled,
    set_notifications_enabled,
    get_language,
    set_language,
    get_code,
)
from app.core.logger import log_event
from app.i18n import get_available_languages
from app.api import fetch_riot_id, enable_mfa, verify_mfa
from app.ui.toast import Toast
from app.ui.account_card import AccountCard
from app.ui.manual_add_dialog import ManualAddDialog
from app.ui.login_browser_dialog import LoginBrowserDialog
from app.ui.password_dialog import PasswordResetDialog


def _safe_log(event: str, **kwargs) -> None:
    try:
        log_event(event, **kwargs)
    except Exception:
        pass


def _create_lock_icon(closed: bool) -> QPixmap:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#4a4a4a" if closed else "#888888")
    painter.setPen(color)

    if closed:
        painter.drawEllipse(6, 14, 12, 10)
        painter.drawRect(7, 8, 10, 8)
        painter.drawLine(12, 8, 12, 5)
        painter.drawArc(9, 2, 6, 6, 0, 180 * 16)
    else:
        painter.drawEllipse(6, 14, 12, 10)
        painter.drawRect(7, 8, 10, 8)
    painter.end()
    return pixmap


class MainWindow(QMainWindow):
    def __init__(self, dek=None, has_password=True):
        super().__init__()
        self.setWindowTitle("Riot 2FA Bypass")
        self.setMinimumSize(560, 300)
        self.resize(560, 400)

        self.dek = dek
        self.has_password = has_password

        if dek is not None:
            self.accounts = load_accounts(dek)
        else:
            self.accounts = load_accounts()
        self.cards: list[AccountCard] = []
        self._last_step = int(time.time()) // PERIOD

        self._setup_menu()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(0)

        hdr = QHBoxLayout()
        title = QLabel("RIOT 2FA")
        title.setObjectName("titleLabel")
        hdr.addWidget(title)
        hdr.addStretch()

        self.lock_icon = QLabel()
        self._update_lock_icon()
        hdr.addWidget(self.lock_icon)

        b1 = QPushButton("Add via Login")
        b1.setObjectName("addLoginBtn")
        b1.setFixedWidth(130)
        b1.clicked.connect(self._add_via_login)
        hdr.addWidget(b1)
        hdr.addSpacing(6)
        b2 = QPushButton("Add Manually")
        b2.setObjectName("addManualBtn")
        b2.setFixedWidth(120)
        b2.clicked.connect(self._add_manually)
        hdr.addWidget(b2)
        outer.addLayout(hdr)
        outer.addSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search accounts...")
        self.search_input.setObjectName("searchInput")
        self.search_input.textChanged.connect(self._on_search_changed)
        outer.addWidget(self.search_input)
        outer.addSpacing(8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QVBoxLayout(self.scroll_area_widget)
        self.scroll_area_layout.setContentsMargins(0, 0, 2, 0)
        self.scroll_area_layout.setSpacing(6)
        self.scroll_area_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_area_widget)
        outer.addWidget(self.scroll_area, stretch=1)

        self.toast = Toast(central)

        self._populate()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(200)

        self._setup_tray()

    def _setup_menu(self):
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")

        reset_action = settings_menu.addAction("Reset Password")
        reset_action.triggered.connect(self._reset_password)

        settings_menu.addSeparator()

        self._minimize_action = settings_menu.addAction("Minimize to tray on close")
        self._minimize_action.setCheckable(True)
        self._minimize_action.setChecked(get_minimize_to_tray())
        self._minimize_action.triggered.connect(self._toggle_minimize_to_tray)

        self._auto_start_action = settings_menu.addAction("Start with Windows")
        self._auto_start_action.setCheckable(True)
        self._auto_start_action.setChecked(get_auto_start())
        self._auto_start_action.triggered.connect(self._toggle_auto_start_menu)

        self._notifications_action = settings_menu.addAction("Desktop notifications")
        self._notifications_action.setCheckable(True)
        self._notifications_action.setChecked(get_notifications_enabled())
        self._notifications_action.triggered.connect(self._toggle_notifications)

        self._language_menu = QMenu("Language", self)
        current_lang = get_language()
        for lang_code, lang_name in get_available_languages().items():
            action = self._language_menu.addAction(lang_name)
            action.setCheckable(True)
            action.setChecked(lang_code == current_lang)
            action.triggered.connect(
                lambda checked, lc=lang_code: self._change_language(lc)
            )
        settings_menu.addMenu(self._language_menu)

        settings_menu.addSeparator()

        logout_action = settings_menu.addAction("Logout")
        logout_action.triggered.connect(self._logout)

        exit_action = settings_menu.addAction("Exit")
        exit_action.triggered.connect(self._quit_completely)

    def _toggle_minimize_to_tray(self, enabled):
        set_minimize_to_tray(enabled)
        self._minimize_action.setChecked(enabled)
        self._update_tray_menu()

    def _toggle_auto_start_menu(self, enabled):
        set_auto_start(enabled)
        self._auto_start_action.setChecked(enabled)
        self._update_tray_menu()

    def _toggle_notifications(self, enabled):
        set_notifications_enabled(enabled)
        self._notifications_action.setChecked(enabled)
        if enabled:
            self._expiry_notified = False

    def _change_language(self, lang_code: str):
        set_language(lang_code)
        self._minimize_action.setChecked(get_minimize_to_tray())
        self._auto_start_action.setChecked(get_auto_start())
        self._notifications_action.setChecked(get_notifications_enabled())
        self._update_tray_menu()

    def _show_notification(self, title: str, message: str) -> None:
        if not get_notifications_enabled():
            return
        if not hasattr(self, "tray"):
            return
        try:
            self.tray.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Information, 3000
            )
        except Exception:
            pass

    def _setup_tray(self):
        icon_path = (
            Path(__file__).parent.parent.parent
            / "assets"
            / "icon"
            / "riot2fa-bypass.ico"
        )
        if icon_path.exists():
            tray_icon = QIcon(str(icon_path))
        else:
            tray_icon = QIcon()
        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip("Riot 2FA Bypass")
        self.tray.activated.connect(self._tray_activated)
        self._update_tray_menu()
        self.tray.show()

    def _update_tray_menu(self):
        menu = QMenu(self)

        show_action = menu.addAction("Show Window")
        show_action.triggered.connect(self._show_from_tray)

        menu.addSeparator()

        copy_menu = menu.addMenu("Copy 2FA Code")
        if self.accounts:
            for acct in self.accounts:
                action = copy_menu.addAction(acct["name"])
                action.triggered.connect(
                    lambda checked, a=acct: self._copy_from_tray(a)
                )
        else:
            copy_menu.setEnabled(False)

        menu.addSeparator()

        settings_menu = menu.addMenu("Settings")
        minimize_action = settings_menu.addAction("Minimize to tray on close")
        minimize_action.setCheckable(True)
        minimize_action.setChecked(get_minimize_to_tray())
        minimize_action.triggered.connect(
            lambda enabled: self._toggle_minimize_to_tray(enabled)
        )

        auto_start_action = settings_menu.addAction("Start with Windows")
        auto_start_action.setCheckable(True)
        auto_start_action.setChecked(get_auto_start())
        auto_start_action.triggered.connect(self._toggle_auto_start_menu)

        notifications_action = settings_menu.addAction("Desktop notifications")
        notifications_action.setCheckable(True)
        notifications_action.setChecked(get_notifications_enabled())
        notifications_action.triggered.connect(self._toggle_notifications)

        tray_lang_menu = QMenu("Language", self)
        current_lang = get_language()
        for lang_code, lang_name in get_available_languages().items():
            action = tray_lang_menu.addAction(lang_name)
            action.setCheckable(True)
            action.setChecked(lang_code == current_lang)
            action.triggered.connect(
                lambda checked, lc=lang_code: self._change_language(lc)
            )
        settings_menu.addMenu(tray_lang_menu)

        menu.addSeparator()

        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self._quit_completely)

        self.tray.setContextMenu(menu)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def _copy_from_tray(self, account):
        from PyQt6.QtWidgets import QApplication

        code = get_code(account["seed"])
        QApplication.clipboard().setText(code)
        _safe_log("code_copied", name=account["name"], method="tray")

        QTimer.singleShot(30000, lambda: QApplication.clipboard().setText(""))

    def _toggle_auto_start(self, enabled):
        set_auto_start(enabled)
        self._auto_start_action.setChecked(enabled)

    def _exit_from_tray(self):
        self.tray.hide()
        self.close()

    def _quit_completely(self):
        self.tray.hide()
        self.setAttribute(0x307, False)  # WA_DeleteOnClose
        self.close()
        import sys

        sys.exit(0)

    def _logout(self):
        from app.core import clear_dek

        clear_dek()
        _safe_log("user_logout")
        self.tray.hide()
        self.setAttribute(0x307, False)
        self.close()
        import sys

        sys.exit(0)

    def closeEvent(self, event):
        if get_minimize_to_tray():
            event.ignore()
            self.hide()
        else:
            self.tray.hide()
            event.accept()

    def _update_lock_icon(self):
        pixmap = _create_lock_icon(self.has_password)
        self.lock_icon.setPixmap(pixmap)
        if self.has_password:
            self.lock_icon.setToolTip(
                "Password protected" + (" - auto-unlock enabled" if self.dek else "")
            )
        else:
            self.lock_icon.setToolTip("No password set - machine-bound encryption only")

    def _reset_password(self):
        dlg = PasswordResetDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.dek:
            self.dek = dlg.dek
            self.has_password = True
            self._update_lock_icon()
            self.accounts = load_accounts(self.dek)
            self._populate()
            _safe_log("password_reset")
            QMessageBox.information(
                self, "Success", "Password has been reset successfully."
            )

    def _on_search_changed(self, text):
        self._populate()

    def _populate(self):
        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards.clear()

        while self.scroll_area_layout.count() > 0:
            item = self.scroll_area_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        search_query = self.search_input.text().strip().lower()
        if search_query:
            filtered = [
                a for a in self.accounts if search_query in a.get("name", "").lower()
            ]
        else:
            filtered = self.accounts

        if not filtered:
            if search_query:
                lbl = QLabel("No accounts match your search")
            elif not self.accounts:
                lbl = QLabel("No accounts yet — add one with the buttons above")
            else:
                lbl = QLabel("No accounts yet — add one with the buttons above")
            lbl.setObjectName("emptyLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_area_layout.addWidget(lbl)
        else:
            for acct in filtered:
                card = AccountCard(
                    acct["name"], acct["seed"], has_password=self.has_password
                )
                card.remove_requested.connect(self._remove_account)
                card.copy_requested.connect(
                    lambda: self.toast.popup("Copied to clipboard")
                )
                self.cards.append(card)
                self.scroll_area_layout.addWidget(card)
        self.scroll_area_layout.addStretch()

    def _tick(self):
        now = time.time()
        elapsed = now % PERIOD
        remaining_frac = 1.0 - elapsed / PERIOD
        remaining_sec = int(PERIOD - elapsed)
        step = int(now // PERIOD)
        code_changed = step != self._last_step
        self._last_step = step

        if (
            self.accounts
            and remaining_sec == 5
            and not getattr(self, "_expiry_notified", False)
        ):
            self._show_notification(
                "Code Expiring Soon", "Your 2FA code will refresh in 5 seconds"
            )
            self._expiry_notified = True
        elif remaining_sec > 20:
            self._expiry_notified = False

        for card in self.cards:
            card.update_bar(remaining_frac, remaining_sec)
            if code_changed:
                card.refresh_code()

    def _save_and_refresh(self):
        save_accounts(self.accounts, self.dek)
        self._populate()
        self._update_tray_menu()

    def _remove_account(self, name, seed):
        self.accounts = [
            a for a in self.accounts if not (a["name"] == name and a["seed"] == seed)
        ]
        self._save_and_refresh()
        _safe_log("account_removed", name=name)
        self._show_notification("Account Removed", f"2FA removed for {name}")

    def _add_via_login(self):
        dlg = LoginBrowserDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cookies = dlg.cookies
        csrf = dlg.csrf_token
        id_tok = dlg.id_token
        if not csrf or not id_tok:
            QMessageBox.warning(
                self, "Error", "Login OK but tokens could not be extracted."
            )
            return

        try:
            name = fetch_riot_id(cookies, csrf)
        except Exception:
            name = "Unknown"

        try:
            seed = enable_mfa(cookies, csrf)
        except Exception as exc:
            QMessageBox.critical(self, "Enable MFA Failed", str(exc))
            return

        try:
            verify_mfa(id_tok, seed)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Verify Warning",
                f"MFA enabled but verification failed:\n{exc}\n\nSeed saved anyway.",
            )

        self.accounts.append({"name": name, "seed": seed})
        self._save_and_refresh()
        _safe_log("account_added", name=name, method="oauth")
        self._show_notification("Account Added", f"2FA added for {name}")
        QMessageBox.information(self, "Success", f"2FA added for {name}")

    def _add_manually(self):
        dlg = ManualAddDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            self.accounts.append(dlg.result_data)
            self._save_and_refresh()
            _safe_log("account_added", name=dlg.result_data["name"], method="manual")
            self._show_notification(
                "Account Added", f"2FA added for {dlg.result_data['name']}"
            )
