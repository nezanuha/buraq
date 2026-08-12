"""
Cryptographic utilities.

Usage:
    from buraq.utils.crypto import get_random_string, constant_time_compare, salted_hmac
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import string

_DEFAULT_ALLOWED_CHARS = string.ascii_letters + string.digits


def get_random_string(length: int = 12, allowed_chars: str = _DEFAULT_ALLOWED_CHARS) -> str:
    """Return a random string of ``length`` characters from ``allowed_chars``."""
    return "".join(secrets.choice(allowed_chars) for _ in range(length))


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(val1.encode(), val2.encode())


def pbkdf2(
    password: str,
    salt: str,
    iterations: int = 1_800_000,
    dklen: int = 32,
    digest=None,
) -> bytes:
    """Derive a key from a password using PBKDF2-HMAC-SHA256."""
    if digest is None:
        digest = hashlib.sha256
    return hashlib.pbkdf2_hmac(
        digest().name,
        password.encode(),
        salt.encode(),
        iterations,
        dklen=dklen,
    )


def salted_hmac(
    key_salt: str, value: str, secret: str = None, algorithm: str = "sha256"
) -> hmac.HMAC:
    """
    Return an HMAC of ``value`` using a key derived from ``key_salt`` and ``secret``.

    If ``secret`` is omitted, uses ``settings.SECRET_KEY``.
    """
    if secret is None:
        from buraq.conf import settings
        secret = settings.SECRET_KEY
    key = hashlib.new(algorithm, (key_salt + secret).encode()).digest()
    return hmac.new(key, msg=value.encode(), digestmod=algorithm)


__all__ = ["get_random_string", "constant_time_compare", "pbkdf2", "salted_hmac"]
