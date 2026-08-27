"""JSON Web Tokens for stateless authentication.

Signed with HMAC using ``SECRET_KEY``, the same key and the same primitive the
rest of the framework already signs with, so there is no new dependency and no
new key to manage. Only the HMAC family is supported: an asymmetric algorithm
needs a keypair rather than a secret, which is a different configuration story.

Verification is pure CPU -- no database, no I/O -- so it neither blocks the
event loop nor costs a query. Loading the user behind a token does cost one, the
same as a session, because a token that outlives a deactivated account should
not still open the door.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from buraq.exceptions import ImproperlyConfigured

#: The digest behind each supported ``alg``. Restricting this to a fixed table
#: is what makes algorithm confusion impossible: a token naming anything else --
#: "none" above all -- is rejected before its signature is even considered.
_ALGORITHMS = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}


class TokenError(Exception):
    """A token was malformed, expired, or not signed by this application."""


def _b64encode(raw: bytes) -> str:
    """base64url with the padding stripped, as JWT requires."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except Exception as exc:  # malformed base64 is just an invalid token
        raise TokenError("token is not valid base64url") from exc


def _config() -> tuple[str, bytes, int]:
    from buraq.conf import settings

    algorithm = getattr(settings, "JWT_ALGORITHM", "HS256")
    if algorithm not in _ALGORITHMS:
        raise ImproperlyConfigured(
            f"JWT_ALGORITHM is {algorithm!r}; supported values are "
            f"{', '.join(sorted(_ALGORITHMS))}."
        )
    secret = getattr(settings, "SECRET_KEY", "") or ""
    if not secret:
        raise ImproperlyConfigured("SECRET_KEY must be set to issue or read tokens.")
    return algorithm, secret.encode(), getattr(settings, "JWT_EXPIRY_MINUTES", 60)


def _sign(signing_input: bytes, secret: bytes, algorithm: str) -> str:
    return _b64encode(hmac.new(secret, signing_input, _ALGORITHMS[algorithm]).digest())


def encode_token(payload: dict[str, Any], *, expires_minutes: int | None = None) -> str:
    """
    Sign ``payload`` and return the token.

    ``exp`` and ``iat`` are filled in from ``JWT_EXPIRY_MINUTES`` unless the
    payload sets them itself.
    """
    algorithm, secret, default_minutes = _config()
    minutes = default_minutes if expires_minutes is None else expires_minutes

    now = int(time.time())
    claims = {"iat": now, "exp": now + minutes * 60, **payload}

    header = _b64encode(
        json.dumps({"alg": algorithm, "typ": "JWT"}, separators=(",", ":")).encode()
    )
    body = _b64encode(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode()
    return f"{header}.{body}.{_sign(signing_input, secret, algorithm)}"


def decode_token(token: str, *, verify_expiry: bool = True) -> dict[str, Any]:
    """
    Verify ``token`` and return its claims, or raise :class:`TokenError`.

    The algorithm is taken from the configuration, never from the token: a token
    is only accepted if it was signed the way this application signs.
    """
    algorithm, secret, _ = _config()

    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("a token has three dot-separated segments")
    header_segment, body_segment, signature = parts

    try:
        header = json.loads(_b64decode(header_segment))
    except (ValueError, TypeError) as exc:
        raise TokenError("token header is not JSON") from exc
    if header.get("alg") != algorithm:
        # Trusting the token's own "alg" is how "none" attacks work.
        raise TokenError(f"token is signed with {header.get('alg')!r}, expected {algorithm!r}")

    expected = _sign(f"{header_segment}.{body_segment}".encode(), secret, algorithm)
    # Constant time: a short-circuiting comparison leaks the signature a byte at
    # a time to anyone able to measure the response.
    if not hmac.compare_digest(expected, signature):
        raise TokenError("signature does not match")

    try:
        claims = json.loads(_b64decode(body_segment))
    except (ValueError, TypeError) as exc:
        raise TokenError("token payload is not JSON") from exc
    if not isinstance(claims, dict):
        raise TokenError("token payload is not an object")

    if verify_expiry:
        expiry = claims.get("exp")
        if expiry is not None and int(time.time()) >= int(expiry):
            raise TokenError("token has expired")
    return claims


def token_for_user(user, *, expires_minutes: int | None = None) -> str:
    """The access token identifying ``user``."""
    return encode_token({"sub": str(user.pk)}, expires_minutes=expires_minutes)


__all__ = ["TokenError", "decode_token", "encode_token", "token_for_user"]
