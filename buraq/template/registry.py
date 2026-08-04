"""
Template tag / filter registry.

Usage in any app's templatetags.py::

    from buraq.template import register

    @register.global
    def format_price(amount):
        return f"${amount:,.2f}"

    @register.filter
    def truncate(value, length=100):
        return value[:length] + "…" if len(value) > length else value

    @register.test
    def even(value):
        return value % 2 == 0

    # Explicit name override
    @register.global(name="url")
    def my_url_helper(name, **kwargs):
        from buraq.urls import reverse
        return reverse(name, **kwargs)

    # Mark a filter safe (disables auto-escaping for its output)
    @register.filter(is_safe=True)
    def highlight(value, term):
        return value.replace(term, f"<mark>{term}</mark>")
"""
from __future__ import annotations

from collections.abc import Callable


class Library:
    """
    Collects globals, filters, and tests registered via decorators.
    One shared instance is created at module level and applied to the
    Jinja2 environment at startup.
    """

    def __init__(self):
        self._globals: dict[str, Callable] = {}
        self._filters: dict[str, Callable] = {}
        self._tests:   dict[str, Callable] = {}

    # ── @register.global ──────────────────────────────────────────────────────

    def global_(self, func: Callable = None, *, name: str = None, is_safe: bool = False):
        """
        Register a function as a Jinja2 global (callable from any template).

        Can be used as:
            @register.global
            @register.global(name="my_name")
        """
        def decorator(fn: Callable) -> Callable:
            key = name or fn.__name__
            if is_safe:
                from markupsafe import Markup
                original = fn
                def _safe(*args, **kwargs):
                    return Markup(original(*args, **kwargs))
                _safe.__name__ = fn.__name__
                self._globals[key] = _safe
            else:
                self._globals[key] = fn
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    # Alias so users write @register.global (avoids shadowing builtin)
    global_.__name__ = "global"

    # ── @register.filter ──────────────────────────────────────────────────────

    def filter(self, func: Callable = None, *, name: str = None, is_safe: bool = False):
        """
        Register a function as a Jinja2 filter.

        Can be used as:
            @register.filter
            @register.filter(name="my_filter", is_safe=True)
        """
        def decorator(fn: Callable) -> Callable:
            key = name or fn.__name__
            if is_safe:
                from markupsafe import Markup
                original = fn
                def _safe(*args, **kwargs):
                    return Markup(original(*args, **kwargs))
                _safe.__name__ = fn.__name__
                self._filters[key] = _safe
            else:
                self._filters[key] = fn
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    # ── @register.test ────────────────────────────────────────────────────────

    def test(self, func: Callable = None, *, name: str = None):
        """
        Register a function as a Jinja2 test (``{% if x is mytest %}``).

        Can be used as:
            @register.test
            @register.test(name="my_test")
        """
        def decorator(fn: Callable) -> Callable:
            key = name or fn.__name__
            self._tests[key] = fn
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    # ── Apply to a Jinja2 environment ─────────────────────────────────────────

    def apply(self, env) -> None:
        """Apply all collected globals, filters, and tests to *env*."""
        env.globals.update(self._globals)
        env.filters.update(self._filters)
        env.tests.update(self._tests)

    # ── Merge another Library into this one ───────────────────────────────────

    def merge(self, other: Library) -> None:
        self._globals.update(other._globals)
        self._filters.update(other._filters)
        self._tests.update(other._tests)


# Monkeypatch the attribute name so ``@register.global`` works as syntax
# (``global`` is a Python keyword so we can't define the method with that name
#  directly — we use ``global_`` internally and expose it as ``global``).
Library.global_ = Library.global_
setattr(Library, "global", Library.global_)


# ── Shared registry instance ──────────────────────────────────────────────────

_registry = Library()
