"""
TestCase base classes and test utilities for Buraq.

Combine with ``pytest-asyncio`` (recommended) or Python's ``unittest``.

Usage::

    import pytest
    from buraq.test import TestCase

    class TestBlog(TestCase):
        async def asyncSetUp(self):
            self.post = await Post.objects.create(
                title="Hello", slug="hello", content="World", is_published=True
            )

        async def test_list(self):
            response = await self.client.get("/posts/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Hello", response.text)

        async def asyncTearDown(self):
            await Post.objects.filter(slug="hello").delete()
"""
from __future__ import annotations

import asyncio
import contextlib
import unittest
from typing import Any

from buraq.test.client import AsyncClient


# ── override_settings ─────────────────────────────────────────────────────────

class override_settings:
    """
    Temporarily replace settings values in tests.

    Can be used as a context manager or a decorator (sync and async)::

        with override_settings(DEBUG=True, CACHE_BACKEND="buraq.contrib.cache.backends.memory.MemoryCache"):
            ...

        @override_settings(DEBUG=False)
        async def test_production_mode(self):
            ...
    """

    def __init__(self, **kwargs):
        self._overrides = kwargs
        self._original: dict[str, Any] = {}

    def _apply(self):
        from buraq.conf import settings
        from buraq.signals import setting_changed
        for key, new_value in self._overrides.items():
            self._original[key] = getattr(settings, key, None)
            object.__setattr__(settings, key, new_value)
            # Fire setting_changed synchronously (tests are usually in sync context)
            try:
                asyncio.get_event_loop().run_until_complete(
                    setting_changed.send(sender=settings.__class__, setting=key, value=new_value, enter=True)
                )
            except RuntimeError:
                pass  # no running loop — skip signal

    def _restore(self):
        from buraq.conf import settings
        from buraq.signals import setting_changed
        for key, old_value in self._original.items():
            object.__setattr__(settings, key, old_value)
            try:
                asyncio.get_event_loop().run_until_complete(
                    setting_changed.send(sender=settings.__class__, setting=key, value=old_value, enter=False)
                )
            except RuntimeError:
                pass
        self._original.clear()

    def __enter__(self):
        self._apply()
        return self

    def __exit__(self, *args):
        self._restore()

    def __call__(self, func):
        import functools
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                self._apply()
                try:
                    return await func(*args, **kwargs)
                finally:
                    self._restore()
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                self._apply()
                try:
                    return func(*args, **kwargs)
                finally:
                    self._restore()
            return sync_wrapper


# ── TestCase base classes ─────────────────────────────────────────────────────

class SimpleTestCase(unittest.TestCase):
    """
    TestCase that provides assertion helpers but no database or client.

    Suitable for testing pure functions, validators, utilities, etc.
    """

    def assertStatusCode(self, response, code: int) -> None:
        self.assertEqual(
            response.status_code, code,
            f"Expected HTTP {code}, got {response.status_code}."
        )

    def assertContains(self, response, text: str, status_code: int = 200, msg: str = None) -> None:
        self.assertStatusCode(response, status_code)
        self.assertIn(text, response.text, msg or f"'{text}' not found in response.")

    def assertNotContains(self, response, text: str, status_code: int = 200) -> None:
        self.assertStatusCode(response, status_code)
        self.assertNotIn(text, response.text, f"'{text}' unexpectedly found in response.")

    def assertRedirects(
        self,
        response,
        expected_url: str,
        status_code: int = 302,
        msg_prefix: str = "",
    ) -> None:
        self.assertIn(
            response.status_code, (301, 302, 303, 307, 308),
            f"{msg_prefix}Expected a redirect, got HTTP {response.status_code}."
        )
        location = response.headers.get("location", "")
        self.assertEqual(
            location, expected_url,
            f"{msg_prefix}Expected redirect to '{expected_url}', got '{location}'."
        )

    def assertFormError(self, form, field: str | None, errors) -> None:
        """
        Assert that a form field has the given error(s).

        ``field`` can be None to check non-field errors.
        ``errors`` can be a string or a list of strings.
        """
        from buraq.exceptions import NON_FIELD_ERRORS

        if field is None:
            form_errors = form.non_field_errors() if hasattr(form, "non_field_errors") else form.errors.get(NON_FIELD_ERRORS, [])
        else:
            form_errors = form.errors.get(field, [])

        if isinstance(errors, str):
            errors = [errors]

        for error in errors:
            self.assertIn(
                error, form_errors,
                f"Error '{error}' not found in form{'.' if field is None else f' field {field!r}.'} "
                f"Actual errors: {form_errors}"
            )

    def assertJSONEqual(self, response, expected: dict | list) -> None:
        self.assertEqual(response.json(), expected)

    def assertHTMLEqual(self, html1: str, html2: str, msg: str = None) -> None:
        """Compare two HTML strings ignoring whitespace differences."""
        import re
        def _normalize(h):
            return re.sub(r"\s+", " ", h).strip()
        self.assertEqual(_normalize(html1), _normalize(html2), msg)

    def assertRaisesMessage(self, expected_exception, expected_message, *args, **kwargs):
        return _AssertRaisesMessageContext(self, expected_exception, expected_message)


class _AssertRaisesMessageContext(contextlib.AbstractContextManager):
    def __init__(self, test_case, expected_exception, expected_message):
        self.test_case = test_case
        self.expected_exception = expected_exception
        self.expected_message = expected_message

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.test_case.fail(f"{self.expected_exception.__name__} not raised")
        if not issubclass(exc_type, self.expected_exception):
            return False
        self.test_case.assertIn(self.expected_message, str(exc_val))
        return True


class _AsyncMixin:
    """
    Mixin that bridges ``asyncSetUp`` / ``asyncTearDown`` with ``unittest``.

    Subclasses can define ``async def asyncSetUp`` and ``async def asyncTearDown``
    and they will be called correctly.
    """

    def setUp(self):
        super().setUp()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            if hasattr(self, "asyncSetUp"):
                self._loop.run_until_complete(self.asyncSetUp())
        except Exception:
            self._loop.close()
            raise

    def tearDown(self):
        try:
            if hasattr(self, "asyncTearDown"):
                self._loop.run_until_complete(self.asyncTearDown())
        finally:
            self._loop.close()
        super().tearDown()

    def _callTestMethod(self):
        import inspect
        method = getattr(self, self._testMethodName)
        if inspect.iscoroutinefunction(method):
            self._loop.run_until_complete(method())
        else:
            method()


class TestCase(_AsyncMixin, SimpleTestCase):
    """
    Full async test case with an ``AsyncClient`` and database access.

    Usage::

        class BlogTests(TestCase):
            async def asyncSetUp(self):
                self.post = await Post.objects.create(title="Hi", slug="hi", content=".")

            async def test_index(self):
                response = await self.client.get("/")
                self.assertContains(response, "Hi")
    """

    client_class = AsyncClient
    app = None

    def setUp(self):
        super().setUp()
        self.client = self.client_class(self.app)


class TransactionTestCase(TestCase):
    """
    Like ``TestCase`` but wraps each test in a transaction that is rolled back
    after the test completes.  Use when a test modifies data that must be
    isolated from other tests.

    Note: requires a database that supports savepoints (PostgreSQL, MySQL).
    SQLite savepoints are limited — prefer ``TestCase`` for most situations.
    """
