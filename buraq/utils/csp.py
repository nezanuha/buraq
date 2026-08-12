"""
Content Security Policy utilities.

Build and validate CSP header values programmatically.

Usage::

    from buraq.utils.csp import CSP

    policy = CSP(
        default_src=["'self'"],
        script_src=["'self'", "https://cdn.example.com"],
        style_src=["'self'", "'unsafe-inline'"],
        img_src=["'self'", "data:"],
        font_src=["'self'"],
        connect_src=["'self'"],
        frame_ancestors=["'none'"],
        upgrade_insecure_requests=True,
    )
    header_value = policy.as_header()
    # → "default-src 'self'; script-src 'self' https://cdn.example.com; ..."

Keyword arguments map directly to CSP directives — underscores are converted to
hyphens (``default_src`` → ``default-src``).  Values may be:

- A list of strings: directive with space-separated values.
- ``True`` / a bare string: value-less directive flag (e.g. ``upgrade-insecure-requests``).
- ``False`` or ``None``: directive is omitted entirely.
"""
from __future__ import annotations

import secrets
from typing import Any


class CSP:
    """
    Immutable Content Security Policy descriptor.

    Instantiate with keyword arguments mapping directive names (underscores as
    separator) to their values.  Call ``as_header()`` to get the complete
    ``Content-Security-Policy`` header value.

    Special values:

    - ``nonce=True`` — generates a fresh random nonce and exposes it via
      the ``nonce`` property.  The placeholder ``{nonce}`` in any string
      value is replaced with the generated nonce.

    Example::

        policy = CSP(
            default_src=["'self'"],
            script_src=["'self'", "'nonce-{nonce}'"],
            nonce=True,
        )
        print(policy.nonce)          # "abc123..."
        print(policy.as_header())    # "default-src 'self'; script-src 'self' 'nonce-abc123...'"
    """

    def __init__(self, **directives: Any):
        use_nonce = directives.pop("nonce", False)
        self._nonce: str | None = secrets.token_urlsafe(16) if use_nonce else None
        self._directives: dict[str, Any] = directives

    @property
    def nonce(self) -> str | None:
        """The per-request nonce value, or ``None`` if nonces are not enabled."""
        return self._nonce

    def as_header(self) -> str:
        """Render the CSP header value string."""
        parts: list[str] = []
        for key, value in self._directives.items():
            directive = key.replace("_", "-")
            if value is False or value is None:
                continue
            if value is True:
                parts.append(directive)
            elif isinstance(value, (list, tuple)):
                rendered = " ".join(
                    v.replace("{nonce}", self._nonce or "") if isinstance(v, str) else str(v)
                    for v in value
                )
                parts.append(f"{directive} {rendered}")
            else:
                rendered = str(value).replace("{nonce}", self._nonce or "")
                parts.append(f"{directive} {rendered}")
        return "; ".join(parts)

    def update(self, **overrides: Any) -> "CSP":
        """Return a new ``CSP`` with the given directives merged/replaced."""
        merged = dict(self._directives)
        merged.update(overrides)
        if self._nonce is not None:
            merged["nonce"] = True
        return CSP(**merged)

    def __repr__(self) -> str:
        return f"CSP({self.as_header()!r})"
