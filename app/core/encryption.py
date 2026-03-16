import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

PBKDF2_ITERATIONS = 1_200_000
KEY_SIZE = 32
NONCE_SIZE = 12
SALT_SIZE = 16


def generate_dek() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def generate_salt() -> bytes:
    return os.urandom(SALT_SIZE)


def derive_kek(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    nonce = os.urandom(NONCE_SIZE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, b"")


def decrypt(ciphertext: bytes, key: bytes) -> bytes:
    return AESGCM(key).decrypt(ciphertext[:NONCE_SIZE], ciphertext[NONCE_SIZE:], b"")
