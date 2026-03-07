import os
import json

APPDATA_DIR = os.path.join(os.getenv("APPDATA"), "Riot2FA")
ACCOUNTS_FILE = os.path.join(APPDATA_DIR, "accounts.json")


def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_accounts(accounts):
    os.makedirs(APPDATA_DIR, exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)
