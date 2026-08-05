"""
TestCase base classes for Buraq.

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

        async def test_detail(self):
            response = await self.client.get("/posts/hello/")
            self.assertEqual(response.status_code, 200)

        async def asyncTearDown(self):
            await Post.objects.filter(slug="hello").delete()
"""
from __future__ import annotations

import asyncio
import unittest

from buraq.test.client import AsyncClient


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

    def assertContains(self, response, text: str, status_code: int = 200) -> None:
        self.assertStatusCode(response, status_code)
        self.assertIn(text, response.text, f"'{text}' not found in response.")

    def assertNotContains(self, response, text: str, status_code: int = 200) -> None:
        self.assertStatusCode(response, status_code)
        self.assertNotIn(text, response.text, f"'{text}' unexpectedly found in response.")

    def assertRedirects(self, response, expected_url: str) -> None:
        self.assertIn(
            response.status_code, (301, 302, 303, 307, 308),
            f"Expected a redirect, got HTTP {response.status_code}."
        )
        location = response.headers.get("location", "")
        self.assertEqual(location, expected_url, f"Expected redirect to '{expected_url}'.")

    def assertJSONEqual(self, response, expected: dict | list) -> None:
        self.assertEqual(response.json(), expected)


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
        if hasattr(self, "asyncSetUp"):
            self._loop.run_until_complete(self.asyncSetUp())

    def tearDown(self):
        if hasattr(self, "asyncTearDown"):
            self._loop.run_until_complete(self.asyncTearDown())
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
