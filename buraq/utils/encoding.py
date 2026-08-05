"""
Encoding utilities — force_str, force_bytes, URI helpers.

Usage:
    from buraq.utils.encoding import force_str, force_bytes, iri_to_uri
"""
from __future__ import annotations

from urllib.parse import quote, unquote


def force_str(value, encoding: str = "utf-8", errors: str = "strict") -> str:
    """Coerce ``value`` to a str. Decodes bytes using ``encoding``."""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode(encoding, errors)
    return str(value)


# Alias
smart_str = force_str


def force_bytes(value, encoding: str = "utf-8", errors: str = "strict") -> bytes:
    """Coerce ``value`` to bytes. Encodes str using ``encoding``."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode(encoding, errors)
    return str(value).encode(encoding, errors)


def iri_to_uri(iri: str | None) -> str:
    """
    Convert an IRI (Internationalized Resource Identifier) to a safe URI.

    Non-ASCII characters are percent-encoded; already-encoded sequences
    and safe URI characters are left alone.
    """
    if iri is None:
        return ""
    # RFC 3987 safe characters that should not be encoded in a URI
    safe = "/:@!$&'()*+,;=~%-._"
    return quote(force_str(iri), safe=safe)


def uri_to_iri(uri: str | None) -> str:
    """Convert a URI to an IRI by unquoting percent-encoded sequences."""
    if uri is None:
        return ""
    return unquote(force_str(uri))


def escape_uri_path(path: str) -> str:
    """
    Percent-encode a URI path, leaving slashes intact.

    Safe for use in ``Location`` response headers.
    """
    return quote(force_str(path), safe="/:@!$&'()*+,;=~%-._")


__all__ = [
    "force_str", "smart_str", "force_bytes",
    "iri_to_uri", "uri_to_iri", "escape_uri_path",
]
