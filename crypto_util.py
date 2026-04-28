"""
crypto_util.py — password encryption for stored sessions.

Uses Fernet symmetric encryption (cryptography package, already a
dependency via paramiko). The key is derived from a machine-specific
ID so passwords encrypted on one machine won't decrypt on another,
and the key is never stored anywhere.

Falls back gracefully for existing plaintext passwords.
"""
from __future__ import annotations
import base64
import hashlib
import logging
import os
import platform

log = logging.getLogger(__name__)


def _machine_key() -> bytes:
    """Derive a stable 32-byte key from machine-specific data."""
    sources = []

    # /etc/machine-id (Linux standard)
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path) as f:
                val = f.read().strip()
                if val:
                    sources.append(val); break
        except OSError:
            pass

    # Fallback: hostname + username
    if not sources:
        sources.append(platform.node())
        sources.append(os.environ.get("USER", os.environ.get("USERNAME", "tunnelrat")))

    combined = "|".join(sources) + "|TunnelRAT-v1"
    raw = hashlib.sha256(combined.encode()).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_password(plaintext: str) -> str:
    """Return encrypted ciphertext, or '' for empty input."""
    if not plaintext:
        return ""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_machine_key())
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        log.warning("Password encryption failed, storing plaintext: %s", e)
        return plaintext


def decrypt_password(stored: str) -> str:
    """Return plaintext. Handles both encrypted and legacy plaintext values."""
    if not stored:
        return ""
    try:
        from cryptography.fernet import Fernet, InvalidToken
        f = Fernet(_machine_key())
        return f.decrypt(stored.encode()).decode()
    except Exception:
        # Not a Fernet token — assume legacy plaintext
        return stored
