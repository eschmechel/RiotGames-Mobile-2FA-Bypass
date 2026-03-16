import base64
import json
import os
from pathlib import Path
from typing import Any

from app.core.encryption import encrypt, decrypt

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

    if dek is None:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        encrypted_data = json.load(f)

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
