"""
Cryptographic signing utilities — sign and verify data using HMAC-SHA256.

Signs values so they can round-trip through untrusted storage.

Usage::

    from buraq.utils.signing import Signer, TimestampSigner, dumps, loads

    # Simple signing
    signer = Signer()
    signed = signer.sign("hello")        # "hello:Zm9v..."
    value  = signer.unsign(signed)       # "hello"

    # With expiry
    ts = TimestampSigner()
    signed = ts.sign("hello")
    value  = ts.unsign(signed, max_age=60)   # raises SignatureExpired after 60 s

    # Serialize arbitrary data
    token = dumps({"user_id": 42, "action": "activate"})
    data  = loads(token, max_age=3600)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class BadSignature(Exception):
    """Raised when a signature does not match."""


class SignatureExpired(BadSignature):
    """Raised when a :class:`TimestampSigner` value is too old."""


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _get_key() -> bytes:
    from buraq.conf import settings
    secret = getattr(settings, "SECRET_KEY", "")
    if not secret:
        raise RuntimeError("SECRET_KEY must be set in settings before using signing utilities.")
    return secret.encode()


class Signer:
    """
    Sign and verify strings using HMAC-SHA256.

    Args:
        key:       Override ``settings.SECRET_KEY``.
        sep:       Separator between value and signature (default ``":"``).
        salt:      Extra entropy mixed into the key (default ``"buraq.utils.signing"``).
        algorithm: Hash algorithm name (default ``"sha256"``).
    """

    def __init__(
        self,
        key: str | None = None,
        sep: str = ":",
        salt: str = "buraq.utils.signing",
        algorithm: str = "sha256",
    ) -> None:
        self._key = key
        self.sep = sep
        self.salt = salt
        self.algorithm = algorithm

        if sep in _b64_encode(b"x"):
            raise ValueError(
                f"Unsafe sep {sep!r} — it appears in base64 output"
                f" and cannot be used as a separator."
            )

    def _signing_key(self) -> bytes:
        key = self._key.encode() if self._key else _get_key()
        return hashlib.sha256(self.salt.encode() + key).digest()

    def _make_signature(self, value: str) -> str:
        sig = hmac.new(self._signing_key(), value.encode(), self.algorithm).digest()
        return _b64_encode(sig)

    def sign(self, value: str) -> str:
        """Return ``value`` with a signature appended: ``"value:sig"``."""
        sig = self._make_signature(value)
        return f"{value}{self.sep}{sig}"

    def unsign(self, signed_value: str) -> str:
        """
        Verify the signature and return the original value.

        Raises :class:`BadSignature` if verification fails.
        """
        if self.sep not in signed_value:
            raise BadSignature(f"No {self.sep!r} found in value")
        value, sig = signed_value.rsplit(self.sep, 1)
        expected = self._make_signature(value)
        if not hmac.compare_digest(sig.encode(), expected.encode()):
            raise BadSignature(f"Signature {sig!r} does not match")
        return value

    def sign_object(self, obj: Any, serializer=json, compress: bool = False) -> str:
        """Serialize *obj* to JSON, optionally compress, and sign."""
        data = serializer.dumps(obj, separators=(",", ":"))
        if isinstance(data, str):
            data = data.encode()
        if compress:
            import zlib
            data = zlib.compress(data)
        encoded = _b64_encode(data)
        return self.sign(encoded)

    def unsign_object(self, signed_value: str, serializer=json) -> Any:
        """Unsign and deserialize a value created by :meth:`sign_object`."""
        encoded = self.unsign(signed_value)
        try:
            data = _b64_decode(encoded)
        except Exception as e:
            raise BadSignature("Encoded value is not valid base64") from e
        # Try decompressing — fall back to raw bytes if not compressed
        try:
            import zlib
            data = zlib.decompress(data)
        except Exception:
            pass
        try:
            return serializer.loads(data)
        except Exception as e:
            raise BadSignature("Could not deserialize signed object") from e


class TimestampSigner(Signer):
    """
    Like :class:`Signer`, but embeds a UTC timestamp so you can enforce expiry.

    Args:
        key, sep, salt, algorithm: Same as :class:`Signer`.
    """

    def sign(self, value: str) -> str:
        """Return ``"value:timestamp:sig"``."""
        ts = _b64_encode(str(int(time.time())).encode())
        value_ts = f"{value}{self.sep}{ts}"
        sig = self._make_signature(value_ts)
        return f"{value_ts}{self.sep}{sig}"

    def unsign(self, signed_value: str, max_age: int | float | None = None) -> str:
        """
        Verify the signature and, if *max_age* is given, check the timestamp.

        Args:
            signed_value: The full signed string.
            max_age:      Maximum age in **seconds**. ``None`` skips expiry check.

        Raises:
            :class:`SignatureExpired` if the value is older than *max_age*.
            :class:`BadSignature`     if the signature is invalid.
        """
        result = super().unsign(signed_value)
        # result is "value:timestamp"
        if self.sep not in result:
            raise BadSignature("Malformed timestamp signed value")
        value, ts_b64 = result.rsplit(self.sep, 1)
        try:
            ts = int(_b64_decode(ts_b64))
        except Exception as e:
            raise BadSignature("Malformed timestamp") from e

        if max_age is not None:
            age = time.time() - ts
            if age > max_age:
                raise SignatureExpired(
                    f"Signature age {age:.1f}s > max_age {max_age}s"
                )
        return value

    def sign_object(self, obj: Any, serializer=json, compress: bool = False) -> str:
        data = serializer.dumps(obj, separators=(",", ":"))
        if isinstance(data, str):
            data = data.encode()
        if compress:
            import zlib
            data = zlib.compress(data)
        encoded = _b64_encode(data)
        return self.sign(encoded)

    def unsign_object(
        self, signed_value: str, serializer=json, max_age: int | float | None = None
    ) -> Any:
        encoded = self.unsign(signed_value, max_age=max_age)
        try:
            data = _b64_decode(encoded)
        except Exception as e:
            raise BadSignature("Encoded value is not valid base64") from e
        try:
            import zlib
            data = zlib.decompress(data)
        except Exception:
            pass
        try:
            return serializer.loads(data)
        except Exception as e:
            raise BadSignature("Could not deserialize signed object") from e


def dumps(
    obj: Any,
    key: str | None = None,
    salt: str = "buraq.utils.signing",
    serializer=json,
    compress: bool = False,
) -> str:
    """
    Serialize *obj* and return a URL-safe, signed string.

    Example::

        token = dumps({"user_id": 42, "action": "activate"})
        # pass token in an email link or cookie

    Args:
        obj:        JSON-serializable object.
        key:        Override ``settings.SECRET_KEY``.
        salt:       Extra entropy (use different salts for different purposes).
        serializer: JSON-compatible module (default: :mod:`json`).
        compress:   If ``True``, zlib-compress before encoding.
    """
    return TimestampSigner(key=key, salt=salt).sign_object(
        obj, serializer=serializer, compress=compress
    )


def loads(
    s: str,
    key: str | None = None,
    salt: str = "buraq.utils.signing",
    serializer=json,
    max_age: int | float | None = None,
) -> Any:
    """
    Verify and deserialize a value created by :func:`dumps`.

    Args:
        s:          Signed string from :func:`dumps`.
        key:        Override ``settings.SECRET_KEY``.
        salt:       Must match the salt used in :func:`dumps`.
        serializer: JSON-compatible module.
        max_age:    Maximum age in **seconds** before raising :class:`SignatureExpired`.

    Raises:
        :class:`BadSignature` if verification fails.
        :class:`SignatureExpired` if older than *max_age*.
    """
    return TimestampSigner(key=key, salt=salt).unsign_object(
        s, serializer=serializer, max_age=max_age
    )


__all__ = [
    "Signer",
    "TimestampSigner",
    "BadSignature",
    "SignatureExpired",
    "dumps",
    "loads",
]
