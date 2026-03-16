import re
import keyring
import keyring.errors
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()
SERVICE = "Riot2FA"
DEK_KEY = "dek"

FAILED_ATTEMPTS: int = 0
LOCKOUT_UNTIL: float | None = None


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 128:
        return "Password must be 128 characters or fewer."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:',.<>?/`~]", password):
        return "Password must contain at least one special character."
    return None


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(stored_hash: str, password: str) -> tuple[bool, bool]:
    try:
        ph.verify(stored_hash, password)
        needs_rehash = ph.check_needs_rehash(stored_hash)
        return True, needs_rehash
    except VerifyMismatchError:
        return False, False


def store_dek(dek: bytes) -> bool:
    try:
        keyring.set_password(SERVICE, DEK_KEY, dek.hex())
        return True
    except keyring.errors.PasswordSetError:
        return False


def load_dek() -> bytes | None:
    try:
        val = keyring.get_password(SERVICE, DEK_KEY)
        return bytes.fromhex(val) if val else None
    except Exception:
        return None


def clear_dek() -> None:
    try:
        keyring.delete_password(SERVICE, DEK_KEY)
    except keyring.errors.PasswordDeleteError:
        pass


def get_failed_attempts() -> int:
    return FAILED_ATTEMPTS


def increment_failed_attempts() -> None:
    global FAILED_ATTEMPTS
    FAILED_ATTEMPTS += 1


def reset_failed_attempts() -> None:
    global FAILED_ATTEMPTS, LOCKOUT_UNTIL
    FAILED_ATTEMPTS = 0
    LOCKOUT_UNTIL = None


def get_lockout_until() -> float | None:
    return LOCKOUT_UNTIL


def set_lockout_until(timestamp: float) -> None:
    global LOCKOUT_UNTIL
    LOCKOUT_UNTIL = timestamp
