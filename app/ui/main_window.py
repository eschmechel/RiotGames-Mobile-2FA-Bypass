import time

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
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor

from app.core import load_accounts, save_accounts, PERIOD
from app.core.logger import log_event
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
        self.setWindowTitle("Riot 2FA")
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
        outer.addSpacing(12)

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
        self.timer.start(50)

    def _setup_menu(self):
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")

        reset_action = settings_menu.addAction("Reset Password")
        reset_action.triggered.connect(self._reset_password)

        settings_menu.addSeparator()

        exit_action = settings_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

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

        if not self.accounts:
            lbl = QLabel("No accounts yet — add one with the buttons above")
            lbl.setObjectName("emptyLabel")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_area_layout.addWidget(lbl)
        else:
            for acct in self.accounts:
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

        for card in self.cards:
            card.update_bar(remaining_frac, remaining_sec)
            if code_changed:
                card.refresh_code()

    def _save_and_refresh(self):
        save_accounts(self.accounts, self.dek)
        self._populate()

    def _remove_account(self, name, seed):
        self.accounts = [
            a for a in self.accounts if not (a["name"] == name and a["seed"] == seed)
        ]
        self._save_and_refresh()
        _safe_log("account_removed", name=name)

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
        QMessageBox.information(self, "Success", f"2FA added for {name}")

    def _add_manually(self):
        dlg = ManualAddDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            self.accounts.append(dlg.result_data)
            self._save_and_refresh()
            _safe_log("account_added", name=dlg.result_data["name"], method="manual")
