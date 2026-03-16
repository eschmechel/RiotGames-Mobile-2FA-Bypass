import base64
import json
import os
import sys
from typing import Any

from app.core.encryption import encrypt, decrypt
from app.core.logger import log_event

APPDATA_DIR = os.path.join(os.getenv("APPDATA") or "", "Riot2FA")
ACCOUNTS_FILE = os.path.join(APPDATA_DIR, "accounts.json")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")
CONFIG_VERSION = 2


def _guard_appdata() -> None:
    if not APPDATA_DIR or not os.path.dirname(APPDATA_DIR):
        raise RuntimeError("APPDATA environment variable is not set. Cannot proceed.")


def is_first_run() -> bool:
    _guard_appdata()
    return not os.path.exists(CONFIG_FILE)


def needs_migration() -> bool:
    """Check if accounts.json contains plaintext data that needs migration."""
    _guard_appdata()
    if not os.path.exists(ACCOUNTS_FILE):
        return False
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return isinstance(data, list) and len(data) > 0
    except (json.JSONDecodeError, OSError):
        return False


def detect_legacy() -> bool:
    _guard_appdata()
    if not os.path.exists(ACCOUNTS_FILE):
        return False
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return isinstance(data, list) or data.get("version", 2) != CONFIG_VERSION
    except (json.JSONDecodeError, OSError):
        return True


def load_config() -> dict[str, Any] | None:
    _guard_appdata()
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_config(config: dict[str, Any]) -> None:
    _guard_appdata()
    os.makedirs(APPDATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_accounts(dek: bytes | None = None) -> list[dict[str, Any]]:
    _guard_appdata()
    if not os.path.exists(ACCOUNTS_FILE):
        return []

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        encrypted_data = json.load(f)

    if isinstance(encrypted_data, list):
        accounts: list[dict[str, Any]] = encrypted_data
        if dek is not None and len(accounts) > 0:
            plaintext = json.dumps(accounts, ensure_ascii=False).encode("utf-8")
            ciphertext = encrypt(plaintext, dek)
            wrapped = {
                "version": CONFIG_VERSION,
                "data": base64.b64encode(ciphertext).decode("utf-8"),
            }
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(wrapped, f, indent=2, ensure_ascii=False)
        return accounts

    if dek is None:
        return []

    if encrypted_data.get("version") != CONFIG_VERSION:
        return []

    try:
        ciphertext = base64.b64decode(encrypted_data["data"])
        plaintext = decrypt(ciphertext, dek)
        return json.loads(plaintext.decode("utf-8"))
    except Exception:
        return []


def save_accounts(accounts: list[dict[str, Any]], dek: bytes | None = None) -> None:
    _guard_appdata()
    os.makedirs(APPDATA_DIR, exist_ok=True)

    if dek is None:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
        return

    plaintext = json.dumps(accounts, ensure_ascii=False).encode("utf-8")
    ciphertext = encrypt(plaintext, dek)

    encrypted_data = {
        "version": CONFIG_VERSION,
        "data": base64.b64encode(ciphertext).decode("utf-8"),
    }

    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(encrypted_data, f, indent=2, ensure_ascii=False)


def get_minimize_to_tray() -> bool:
    config = load_config()
    return config.get("minimize_to_tray", True) if config else True


def set_minimize_to_tray(enabled: bool) -> None:
    config = load_config() or {}
    config["minimize_to_tray"] = enabled
    save_config(config)


def get_auto_start() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        )
        try:
            winreg.QueryValueEx(key, "Riot2FABypass")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception as e:
        log_event("auto_start_check_failed", error=str(e))
        return False


def set_auto_start(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_WRITE,
        )
        if enabled:
            exe_path = sys.executable
            winreg.SetValueEx(key, "Riot2FABypass", 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, "Riot2FABypass")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        log_event("auto_start_set_failed", error=str(e))


def get_notifications_enabled() -> bool:
    config = load_config()
    return config.get("notifications_enabled", False) if config else False


def set_notifications_enabled(enabled: bool) -> None:
    config = load_config() or {}
    config["notifications_enabled"] = enabled
    save_config(config)
