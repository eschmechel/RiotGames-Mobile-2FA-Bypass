import re

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

from app.api import is_valid_jwt


class LoginBrowserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Riot Account Login")
        self.resize(960, 720)
        self.cookies = {}
        self.csrf_token = None
        self.id_token = None
        self._detected = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.status = QLabel("  Waiting for login...")
        self.status.setFixedHeight(28)
        self.status.setStyleSheet(
            "background-color:#111118; color:#666677; font-size:11px; padding-left:10px;"
        )
        lay.addWidget(self.status)

        self.profile = QWebEngineProfile("riot_2fa_login", self)
        self.profile.cookieStore().deleteAllCookies()
        self.profile.cookieStore().cookieAdded.connect(self._cookie_added)

        self._page = QWebEnginePage(self.profile, self)
        self.browser = QWebEngineView(self)
        self.browser.setPage(self._page)
        lay.addWidget(self.browser)

        self._page.urlChanged.connect(self._url_changed)
        self._page.loadFinished.connect(self._load_finished)
        self.browser.setUrl(QUrl("https://account.riotgames.com/"))

    def _cleanup_browser(self):
        self._page.disconnect()
        self.browser.setPage(None)
        self._page.deleteLater()
        self._page = None

    def done(self, result):
        self._cleanup_browser()
        super().done(result)

    def _cookie_added(self, cookie):
        name = bytes(cookie.name()).decode("utf-8", errors="replace")
        value = bytes(cookie.value()).decode("utf-8", errors="replace")
        self.cookies[name] = value
        if name in ("id_token", "a12l-csrf-prod"):
            QTimer.singleShot(300, self._try_detect)

    def _url_changed(self, url):
        QTimer.singleShot(500, self._try_detect)

    def _load_finished(self, ok):
        if ok:
            QTimer.singleShot(500, self._try_detect)

    def _try_detect(self):
        if self._detected:
            return
        if self._page is None:
            return
        id_tok = self.cookies.get("id_token")
        csrf_ck = self.cookies.get("a12l-csrf-prod")
        if not id_tok or not csrf_ck:
            return
        if not is_valid_jwt(id_tok):
            return
        base = self._page.url().toString().split("?")[0].split("#")[0].rstrip("/")
        if base != "https://account.riotgames.com":
            return
        self._detected = True
        self.id_token = id_tok
        self.status.setText("  Login detected — extracting CSRF token...")
        self.status.setStyleSheet(
            "background-color:#0e1a0e; color:#55aa55; font-size:11px; padding-left:10px;"
        )
        self._page.toHtml(self._html_received)

    def _html_received(self, html):
        m = re.search(
            r"""<meta\s+name=['"]csrf-token['"]\s+content=['"]([^'"]+)['"]""", html
        )
        if m:
            self.csrf_token = m.group(1)
            self.status.setText("  Success!")
            QTimer.singleShot(400, self.accept)
        else:
            self._detected = False
            self.status.setText("  CSRF token not found, retrying...")
            self.status.setStyleSheet(
                "background-color:#1a1a0e; color:#aaaa55; font-size:11px; padding-left:10px;"
            )
            QTimer.singleShot(2000, self._try_detect)
