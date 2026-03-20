"""AES-256-GCM encryption module for vault.dat"""

import os
import json
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


PBKDF2_ITERATIONS = 100_000
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32  # AES-256


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive AES-256 key from master password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(master_password.encode('utf-8'))


def encrypt_data(data: dict, master_password: str) -> bytes:
    """Encrypt a dict to bytes using AES-256-GCM.

    Format: salt(16) + nonce(12) + ciphertext(variable)
    """
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(master_password, salt)

    plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return salt + nonce + ciphertext


def decrypt_data(encrypted: bytes, master_password: str) -> dict:
    """Decrypt bytes back to dict. Raises Exception on wrong password."""
    if len(encrypted) < SALT_SIZE + NONCE_SIZE + 16:
        raise ValueError("Corrupted vault data")

    salt = encrypted[:SALT_SIZE]
    nonce = encrypted[SALT_SIZE:SALT_SIZE + NONCE_SIZE]
    ciphertext = encrypted[SALT_SIZE + NONCE_SIZE:]

    key = derive_key(master_password, salt)
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Wrong master password")

    return json.loads(plaintext.decode('utf-8'))
