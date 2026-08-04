"""
HTTP utilities — mirrors django.utils.http.
"""
from __future__ import annotations

from urllib.parse import urlparse


def url_has_allowed_host_and_scheme(
    url: str | None,
    allowed_hosts: str | set[str],
    require_https: bool = False,
) -> bool:
    """
    Return ``True`` if the URL is safe to redirect to.

    Guards against open redirect attacks by verifying the host is in
    ``allowed_hosts`` and the scheme is http/https.

    Usage::

        from buraq.utils.http import url_has_allowed_host_and_scheme

        next_url = request.query_params.get("next", "/")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={"example.com"}):
            return redirect(next_url)

    Typically used with ``ALLOWED_HOSTS`` from settings::

        from buraq.conf.defaults import settings
        safe = url_has_allowed_host_and_scheme(url, settings.ALLOWED_HOSTS)
    """
    if url is None:
        return False
    if isinstance(allowed_hosts, str):
        allowed_hosts = {allowed_hosts}
    return _is_safe_url(url, allowed_hosts, require_https=require_https)


def _is_safe_url(url: str, allowed_hosts: set[str], require_https: bool = False) -> bool:
    url = url.strip()
    if not url:
        return False

    # Prevent header injection
    if "\r" in url or "\n" in url or "\x00" in url:
        return False

    try:
        url_info = urlparse(url)
    except ValueError:
        return False

    # Reject URLs with embedded credentials (user:pass@host)
    if url_info.username or url_info.password:
        return False

    scheme = url_info.scheme.lower()
    netloc = url_info.netloc.lower()

    # No scheme and no netloc → relative URL
    if not scheme and not netloc:
        # Guard against protocol-relative (//evil.com) and backslash tricks
        bad = ("//", "\\\\", "\\/", "/\\")
        return not any(url.startswith(b) for b in bad)

    # Only http/https allowed
    if scheme not in ("http", "https"):
        return False

    if require_https and scheme != "https":
        return False

    # Strip port from host for comparison
    host = netloc.split(":")[0] if ":" in netloc else netloc

    return host in {h.lower().split(":")[0] for h in allowed_hosts if h and h != "*"}
