import base64
import os

import win32crypt

_ENTROPY = "LHDNAutomation"

def app_data_dir():
    """Determines where data like token caches shoukld be stored.
    Returns a path within APPDATA that is available for this app.
    If APPDATA is not found, fallback to home directory.
    Creates the directory if it does not exist."""
    base = os.getenv("APPDATA") or os.path.expanduser("~") 
    path = os.path.join(base, _ENTROPY)
    os.makedirs(path, exist_ok=True)
    return path

def encrypt(plaintext):
    """DPAPI encrypts the given plaintext string and returns a base64-encoded ciphertext string."""
    if not plaintext:
        return ""
    blob = win32crypt.CryptProtectData(plaintext.encode("utf-8"), _ENTROPY, None, None, None, 0)
    return base64.b64encode(blob).decode("ascii")

def decrypt(ciphertext_b64):
    """Decrypts the given ciphertext using DPAPI and returns the plaintext string."""
    if not ciphertext_b64:
        return ""
    blob = base64.b64decode(ciphertext_b64)
    _, plaintext = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
    return plaintext.decode("utf-8")
