import os
import base64
from cryptography.fernet import Fernet

_key = base64.urlsafe_b64encode(os.getenv("ENCRYPTION_KEY", "").encode()[:32].ljust(32, b"0"))
_fernet = Fernet(_key)


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
