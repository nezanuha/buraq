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
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

# Sentinel — set by deactivate_all() to disable translation entirely
_DEACTIVATED: str = "__deactivated__"

_active_language: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_active_language", default=None
)

_catalogs: dict[str, _gettext.NullTranslations] = {}
_catalog_lock = threading.Lock()


# ── Language state ─────────────────────────────────────────────────────────────

def _get_default_language() -> str:
    from buraq.conf.defaults import settings
    return settings.LANGUAGE_CODE


def get_language() -> str | None:
    """Return the active language code, or None if deactivate_all() was called."""
    lang = _active_language.get()
    if lang is None:
        return _get_default_language()
    if lang == _DEACTIVATED:
        return None
    return lang


def activate(language: str) -> contextvars.Token:
    """Activate a language for the current async context. Returns a token to restore."""
    return _active_language.set(language)


def deactivate(token: contextvars.Token) -> None:
    """Restore the previous language using the token returned by activate()."""
    _active_language.reset(token)


def deactivate_all() -> contextvars.Token:
    """
    Disable translation entirely for the current async context.

    All translation calls will return the original string unchanged.
    Useful in background tasks or management commands that shouldn't translate.
    Restore with ``deactivate(token)``::

        token = deactivate_all()
        _("Hello")   # → "Hello" (untranslated)
        deactivate(token)
    """
    return _active_language.set(_DEACTIVATED)


@contextmanager
def override(language: str) -> Generator[None, None, None]:
    """
    Context manager — temporarily activate a language::

        with override("ar"):
            assert _("Hello") == "مرحبا"
    """
    token = activate(language)
    try:
        yield
    finally:
        deactivate(token)


# ── Locale helpers ─────────────────────────────────────────────────────────────

def to_locale(language: str) -> str:
    """
    Convert a language code to a locale string.

        to_locale("en")     → "en"
        to_locale("en-us")  → "en_US"
        to_locale("zh-hans") → "zh_Hans"
    """
    parts = language.split("-", 1)
    if len(parts) == 1:
        return language.lower()
    lang, region = parts
    # Title-case the region (handles zh-Hans, sr-Latn, etc.)
    return f"{lang.lower()}_{region.title()}"


def check_for_language(lang: str) -> bool:
    """Return True if ``lang`` is in the configured LANGUAGES setting."""
    return lang in get_supported_languages()


def get_supported_languages() -> list[str]:
    """Return list of supported language codes from settings."""
    from buraq.conf.defaults import settings
    return [code for code, _ in getattr(settings, "LANGUAGES", [])]


def get_language_info_list() -> list[dict[str, str]]:
    """Return info for all configured languages — useful for rendering a switcher."""
    from buraq.conf.defaults import settings
    return [
        {"code": code, "name": name}
        for code, name in getattr(settings, "LANGUAGES", [])
    ]


_RTL_LANGUAGES: frozenset[str] = frozenset({
    "ar", "he", "fa", "ur", "ps", "ku", "ckb", "yi", "sd", "dv", "ug",
})


def get_language_bidi(lang: str | None = None) -> bool:
    """Return True if the given (or active) language is right-to-left."""
    active = lang or get_language() or ""
    return active.split("-")[0] in _RTL_LANGUAGES


def translate_url(url: str, lang: str) -> str:
    """
    Rewrite a URL path to the given language prefix.

        translate_url("/about", "ar")   → "/ar/about"
        translate_url("/ar/about", "fr") → "/fr/about"
        translate_url("/ar/about", "en") → "/about"  (en is default)
    """
    from buraq.conf.defaults import settings

    supported = get_supported_languages()
    default: str = getattr(settings, "LANGUAGE_CODE", "en")

    # Strip any existing language prefix
    stripped = url.lstrip("/")
    parts = stripped.split("/", 1)
    if parts[0] in supported:
        bare = f"/{parts[1]}" if len(parts) > 1 and parts[1] else "/"
    else:
        bare = f"/{stripped}" if stripped else "/"

    if lang not in supported:
        return bare
    if lang == default:
        return bare
    return f"/{lang}{bare}"


def get_language_switch_urls(
    request: Any,
    languages: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """
    Return a list of ``{"code", "name", "url"}`` dicts for each language,
    where ``url`` is the current page rewritten for that language.

    Usage in a view::

        context["lang_switcher"] = get_language_switch_urls(request)
    """
    if languages is None:
        languages = get_language_info_list()

    return [
        {
            "code": lang["code"],
            "name": lang["name"],
            "url": translate_url(request.url.path, lang["code"]),
        }
        for lang in languages
    ]


# ── Catalog loading ────────────────────────────────────────────────────────────

def _load_catalog(language: str) -> _gettext.NullTranslations:
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
                    domain="messages",
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
    lang = get_language()
    if lang is None:
        return message
    return _load_catalog(lang).gettext(message)


def _ntranslate(singular: str, plural: str, number: int) -> str:
    lang = get_language()
    if lang is None:
        return singular if number == 1 else plural
    return _load_catalog(lang).ngettext(singular, plural, number)


def _ptranslate(context: str, message: str) -> str:
    lang = get_language()
    if lang is None:
        return message
    result = _load_catalog(lang).pgettext(context, message)
    return result if result is not None else message


def _nptranslate(context: str, singular: str, plural: str, number: int) -> str:
    lang = get_language()
    if lang is None:
        return singular if number == 1 else plural
    result = _load_catalog(lang).npgettext(context, singular, plural, number)
    return result if result is not None else (singular if number == 1 else plural)


def warmup_catalogs() -> None:
    """
    Pre-load all configured language catalogs at startup.

    Call this once during app boot so the first request for each language
    never pays the .mo file-read cost::

        from buraq.utils.translation import warmup_catalogs
        warmup_catalogs()   # in your app factory or lifespan handler
    """
    for lang in get_supported_languages():
        _load_catalog(lang)


def invalidate_cache() -> None:
    """Clear cached catalogs — call after compilemessages."""
    with _catalog_lock:
        _catalogs.clear()


# ── Immediate translation functions ───────────────────────────────────────────

def gettext(message: str) -> str:
    """Translate a string using the active language."""
    return _translate(message)


def ngettext(singular: str, plural: str, number: int) -> str:
    """Translate with pluralization."""
    return _ntranslate(singular, plural, number)


def pgettext(context: str, message: str) -> str:
    """Translate with a disambiguating context (e.g. 'verb' vs 'noun')."""
    return _ptranslate(context, message)


def npgettext(context: str, singular: str, plural: str, number: int) -> str:
    """Translate with both context and pluralization."""
    return _nptranslate(context, singular, plural, number)


def gettext_noop(message: str) -> str:
    """Mark a string for extraction without translating it."""
    return message


# ── Lazy translation proxies ───────────────────────────────────────────────────

class _LazyStr:
    """Base proxy — defers translation until str() is called."""

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


class _LazyGettext(_LazyStr):
    __slots__ = ("_msg",)

    def __init__(self, msg: str) -> None:
        self._msg = msg

    def __str__(self) -> str:
        return _translate(self._msg)

    def __repr__(self) -> str:
        return f"gettext_lazy({self._msg!r})"


class _LazyNgettext(_LazyStr):
    __slots__ = ("_singular", "_plural", "_number")

    def __init__(self, singular: str, plural: str, number: int) -> None:
        self._singular = singular
        self._plural = plural
        self._number = number

    def __str__(self) -> str:
        return _ntranslate(self._singular, self._plural, self._number)

    def __repr__(self) -> str:
        return f"ngettext_lazy({self._singular!r}, {self._plural!r}, {self._number!r})"


class _LazyPgettext(_LazyStr):
    __slots__ = ("_context", "_msg")

    def __init__(self, context: str, msg: str) -> None:
        self._context = context
        self._msg = msg

    def __str__(self) -> str:
        return _ptranslate(self._context, self._msg)

    def __repr__(self) -> str:
        return f"pgettext_lazy({self._context!r}, {self._msg!r})"


class _LazyNpgettext(_LazyStr):
    __slots__ = ("_context", "_singular", "_plural", "_number")

    def __init__(self, context: str, singular: str, plural: str, number: int) -> None:
        self._context = context
        self._singular = singular
        self._plural = plural
        self._number = number

    def __str__(self) -> str:
        return _nptranslate(self._context, self._singular, self._plural, self._number)

    def __repr__(self) -> str:
        return f"npgettext_lazy({self._context!r}, {self._singular!r}, {self._plural!r})"


def gettext_lazy(message: str) -> _LazyGettext:
    """Lazy gettext — evaluated at request time, not import time."""
    return _LazyGettext(message)


def ngettext_lazy(singular: str, plural: str, number: int) -> _LazyNgettext:
    """Lazy ngettext — useful in model Meta for pluralized verbose names."""
    return _LazyNgettext(singular, plural, number)


def pgettext_lazy(context: str, message: str) -> _LazyPgettext:
    """Lazy pgettext — context-disambiguated, evaluated at request time."""
    return _LazyPgettext(context, message)


def npgettext_lazy(context: str, singular: str, plural: str, number: int) -> _LazyNpgettext:
    """Lazy npgettext — context + pluralization, evaluated at request time."""
    return _LazyNpgettext(context, singular, plural, number)


# ── Convenience aliases ────────────────────────────────────────────────────────
_ = gettext
_l = gettext_lazy
_n = ngettext
_p = pgettext
