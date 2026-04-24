import os
import base64
from cryptography.fernet import Fernet

_raw_key = os.getenv("ENCRYPTION_KEY", "")
if not _raw_key or len(_raw_key) < 32:
    raise RuntimeError(
        "ENCRYPTION_KEY env var is missing or shorter than 32 characters. "
        "Set it in Railway to a 32+ character secret."
    )

_key = base64.urlsafe_b64encode(_raw_key.encode()[:32])
_fernet = Fernet(_key)


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
