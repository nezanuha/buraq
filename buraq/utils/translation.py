"""
Buraq i18n — translation utilities.

Usage:
    from buraq.utils.translation import gettext as _, gettext_lazy as _l, ngettext

    # In views (translated immediately at call time)
    message = _("Welcome")

    # In models/forms (translated lazily at request time)
    verbose_name = _l("Post")

    # Pluralization
    label = ngettext("%(count)d item", "%(count)d items", count) % {"count": count}
"""
from __future__ import annotations

import contextvars
import gettext as _gettext
import threading
from pathlib import Path
from typing import Any

_active_language: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_active_language", default=None
)

_catalogs: dict[str, _gettext.NullTranslations] = {}
_catalog_lock = threading.Lock()


def _get_default_language() -> str:
    from buraq.conf.defaults import settings
    return settings.LANGUAGE_CODE


def get_language() -> str:
    """Return the currently active language code."""
    return _active_language.get() or _get_default_language()


def activate(language: str) -> contextvars.Token:
    """Activate a language for the current async context. Returns a token to restore."""
    return _active_language.set(language)


def deactivate(token: contextvars.Token) -> None:
    """Restore the previous language using the token returned by activate()."""
    _active_language.reset(token)


def _load_catalog(language: str) -> _gettext.NullTranslations:
    """Load and cache a .mo translation catalog for the given language."""
    if language in _catalogs:
        return _catalogs[language]

    with _catalog_lock:
        if language in _catalogs:
            return _catalogs[language]

        from buraq.conf.defaults import settings
        locale_paths: list[str] = getattr(settings, "LOCALE_PATHS", [])

        catalog: _gettext.NullTranslations = _gettext.NullTranslations()
        for locale_path in locale_paths:
            try:
                catalog = _gettext.translation(
                    domain="django",
                    localedir=locale_path,
                    languages=[language],
                    codeset="utf-8",
                )
                break
            except FileNotFoundError:
                continue

        _catalogs[language] = catalog
        return catalog


def _translate(message: str) -> str:
    return _load_catalog(get_language()).gettext(message)


def _ntranslate(singular: str, plural: str, number: int) -> str:
    return _load_catalog(get_language()).ngettext(singular, plural, number)


def gettext(message: str) -> str:
    """Translate a string using the active language."""
    return _translate(message)


def ngettext(singular: str, plural: str, number: int) -> str:
    """Translate a string with pluralization."""
    return _ntranslate(singular, plural, number)


def pgettext(context: str, message: str) -> str:
    """Translate with a disambiguating context (e.g. 'verb' vs 'noun')."""
    catalog = _load_catalog(get_language())
    result = catalog.pgettext(context, message)
    return result if result is not None else message


def gettext_noop(message: str) -> str:
    """Mark a string for extraction without translating it."""
    return message


def invalidate_cache() -> None:
    """Clear cached catalogs — call after compilemessages."""
    with _catalog_lock:
        _catalogs.clear()


class _LazyStr:
    """A string proxy that defers translation until str() is called."""

    __slots__ = ("_msg",)

    def __init__(self, msg: str) -> None:
        self._msg = msg

    def __str__(self) -> str:
        return _translate(self._msg)

    def __repr__(self) -> str:
        return f"lazy_gettext({self._msg!r})"

    def __eq__(self, other: Any) -> bool:
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    def __add__(self, other: str) -> str:
        return str(self) + other

    def __radd__(self, other: str) -> str:
        return other + str(self)

    def __mod__(self, other: Any) -> str:
        return str(self) % other

    def __len__(self) -> int:
        return len(str(self))


def gettext_lazy(message: str) -> _LazyStr:
    """Return a lazy translation proxy — evaluated at request time."""
    return _LazyStr(message)


# Convenient aliases matching Django's API
_ = gettext
_l = gettext_lazy
_n = ngettext
_p = pgettext
