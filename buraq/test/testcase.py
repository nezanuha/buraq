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

        with override_settings(
            DEBUG=True,
            CACHE_BACKEND="buraq.contrib.cache.backends.memory.MemoryCacheBackend",
        ):
            ...

        @override_settings(DEBUG=False)
        async def test_production_mode(self):
            ...
    """

    def __init__(self, **kwargs):
        self._overrides = kwargs
        self._original: dict[str, Any] = {}

    def _fire_setting_changed(self, key, value, enter):
        from buraq.conf import settings
        from buraq.signals import setting_changed
        coro = setting_changed.send(
            sender=settings.__class__, setting=key, value=value, enter=enter
        )
        try:
            loop = asyncio.get_running_loop()
            # Inside an async context — schedule as a task (fire-and-forget)
            loop.create_task(coro)
        except RuntimeError:
            # No running loop — sync context, safe to use asyncio.run()
            asyncio.run(coro)

    def _apply(self):
        from buraq.conf import settings
        for key, new_value in self._overrides.items():
            self._original[key] = getattr(settings, key, None)
            object.__setattr__(settings, key, new_value)
            self._fire_setting_changed(key, new_value, enter=True)

    def _restore(self):
        from buraq.conf import settings
        for key, old_value in self._original.items():
            object.__setattr__(settings, key, old_value)
            self._fire_setting_changed(key, old_value, enter=False)
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
            form_errors = (
                form.non_field_errors()
                if hasattr(form, "non_field_errors")
                else form.errors.get(NON_FIELD_ERRORS, [])
            )
        else:
            form_errors = form.errors.get(field, [])

        if isinstance(errors, str):
            errors = [errors]

        for error in errors:
            self.assertIn(
                error, form_errors,
                f"Error '{error}' not found in"
                f" form{'.' if field is None else f' field {field!r}.'} "
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

    def assertInHTML(
        self, needle: str, haystack: str, count: int = None, msg_prefix: str = ""
    ) -> None:
        """
        Assert that an HTML fragment appears in the haystack HTML.

        Uses normalized (whitespace-collapsed) comparison. If ``count`` is given,
        asserts the fragment appears exactly that many times.
        """
        import re
        def _normalize(h):
            return re.sub(r"\s+", " ", h).strip()
        n = _normalize(needle)
        h = _normalize(haystack)
        occurrences = h.count(n)
        if count is not None:
            self.assertEqual(
                occurrences, count,
                f"{msg_prefix}Found {occurrences} instances of {needle!r}"
                f" in haystack (expected {count})."
            )
        else:
            self.assertTrue(
                occurrences > 0,
                f"{msg_prefix}{needle!r} not found in response HTML."
            )

    def assertNumQueries(self, num: int):
        """Context manager that asserts exactly ``num`` SQL queries are executed."""
        return _AssertNumQueriesContext(self, num)

    def assertFormsetError(
        self, formset, form_index: int | None, field: str | None, errors
    ) -> None:
        """Assert that a formset form has the given error(s)."""
        if form_index is None:
            form_errors = formset.non_form_errors()
        else:
            form = formset.forms[form_index]
            form_errors = form.non_field_errors() if field is None else form.errors.get(field, [])

        if isinstance(errors, str):
            errors = [errors]
        for error in errors:
            self.assertIn(
                error, form_errors,
                f"Error {error!r} not found in formset form {form_index} field {field!r}. "
                f"Actual: {form_errors}"
            )

    def assertRaisesMessage(self, expected_exception, expected_message, *args, **kwargs):
        return _AssertRaisesMessageContext(self, expected_exception, expected_message)


class MessagesTestMixin:
    """
    Mixin that adds ``assertMessages()`` to any TestCase subclass.

    Works with Buraq's flash-message middleware.  Messages are read from
    the response's ``_messages`` attribute (set by the test client) or from
    the session directly.

    Usage::

        class MyView(MessagesTestMixin, TestCase):
            async def test_success_message(self):
                response = await self.client.post("/save/", data={...})
                self.assertMessages(response, ["Saved successfully."])
    """

    def assertMessages(self, response, expected_messages, *, ordered=True):
        """
        Assert that exactly ``expected_messages`` appear in the response.

        ``expected_messages`` is a list of message strings (or
        ``(level, text)`` 2-tuples for level-aware assertions).

        When ``ordered=False``, only set membership is checked.
        """
        # Pull messages from the response context or the session cookie.
        actual = _extract_messages(response)

        if not isinstance(expected_messages, (list, tuple)):
            expected_messages = [expected_messages]

        normalized_expected = [
            (m if isinstance(m, tuple) else (None, m))
            for m in expected_messages
        ]
        normalized_actual = [
            (getattr(m, "level", None), str(m))
            for m in actual
        ]

        if ordered:
            # Compare text only (ignore level) when expected has no level.
            for i, (exp_level, exp_text) in enumerate(normalized_expected):
                if i >= len(normalized_actual):
                    self.fail(
                        f"Expected message {exp_text!r} at position {i}, "
                        f"but only {len(normalized_actual)} message(s) in response."
                    )
                act_level, act_text = normalized_actual[i]
                self.assertEqual(
                    act_text, exp_text,
                    f"Message at position {i}: expected {exp_text!r}, got {act_text!r}."
                )
                if exp_level is not None:
                    self.assertEqual(
                        act_level, exp_level,
                        f"Message level at position {i}: expected {exp_level}, got {act_level}."
                    )
        else:
            actual_texts = {t for _, t in normalized_actual}
            for _, exp_text in normalized_expected:
                self.assertIn(
                    exp_text, actual_texts,
                    f"Expected message {exp_text!r} not found. Actual: {list(actual_texts)}"
                )

        self.assertEqual(
            len(actual), len(expected_messages),
            f"Expected {len(expected_messages)} message(s), got {len(actual)}: "
            f"{[str(m) for m in actual]}"
        )


def _extract_messages(response):
    """Extract flash messages from a test response object."""
    # Prefer explicit _messages attribute set by test client.
    if hasattr(response, "_messages"):
        return list(response._messages)
    # Fall back to context variable if response carries a template context.
    if hasattr(response, "context") and response.context:
        ctx = response.context
        if isinstance(ctx, dict) and "messages" in ctx:
            return list(ctx["messages"])
    return []


class captureOnCommitCallbacks(contextlib.AbstractContextManager):
    """
    Context manager that captures ``on_commit()`` callbacks without a real commit.

    Normally ``buraq.db.on_commit()`` callbacks only fire after a database
    transaction commits.  In tests this means they never fire (``TestCase``
    wraps each test in a transaction that is always rolled back).

    Wrap the code under test with this context manager to collect callbacks and
    optionally execute them immediately::

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            await some_view_that_enqueues_email()

        self.assertEqual(len(callbacks), 1)  # one callback registered

    Pass ``execute=False`` (the default) to collect without running.

    The manager patches ``buraq.db.on_commit`` for the duration of the block
    and restores the original after exiting.
    """

    def __init__(self, *, execute: bool = False):
        self.execute = execute
        self.callbacks: list = []
        self._original = None

    def __enter__(self):
        import buraq.db as _db
        self._original = _db.on_commit

        captured = self

        def _fake_on_commit(func, *args, **kwargs):
            captured.callbacks.append(func)
            if captured.execute:
                import asyncio
                import inspect
                if inspect.iscoroutinefunction(func):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(func())
                    except RuntimeError:
                        asyncio.run(func())
                else:
                    func()

        _db.on_commit = _fake_on_commit
        return self.callbacks

    def __exit__(self, *args):
        import buraq.db as _db
        _db.on_commit = self._original


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


class _QueryCounter:
    """Counts SQL statements executed via the SQLAlchemy engine event system."""

    def __init__(self):
        self.count = 0
        self._listener = None

    def start(self):
        from sqlalchemy import event

        from buraq.core.db import engine

        self.count = 0

        def _count(conn, cursor, stmt, params, context, executemany):
            self.count += 1

        event.listen(engine.sync_engine, "before_cursor_execute", _count)
        self._listener = _count

    def stop(self):
        if self._listener is not None:
            from sqlalchemy import event

            from buraq.core.db import engine
            event.remove(engine.sync_engine, "before_cursor_execute", self._listener)
            self._listener = None


class _AssertNumQueriesContext(contextlib.AbstractContextManager):
    """
    Context manager that counts SQL queries.

    Uses SQLAlchemy engine events to intercept statements. Requires the engine
    to be accessible via ``buraq.core.db.engine``.
    """

    def __init__(self, test_case, num: int):
        self.test_case = test_case
        self.num = num
        self._queries: list = []

    def __enter__(self):
        try:
            from sqlalchemy import event

            from buraq.core.db import engine
            @event.listens_for(engine.sync_engine, "before_cursor_execute")
            def _count(conn, cursor, stmt, params, context, executemany):
                self._queries.append(stmt)
            self._listener = _count
        except Exception:
            self._listener = None
        return self

    def __exit__(self, *args):
        try:
            from sqlalchemy import event

            from buraq.core.db import engine
            if self._listener:
                event.remove(engine.sync_engine, "before_cursor_execute", self._listener)
        except Exception:
            pass
        self.test_case.assertEqual(
            len(self._queries), self.num,
            f"Expected {self.num} SQL queries, got {len(self._queries)}."
        )


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

    def setUp(self):
        super().setUp()
        self._loop.run_until_complete(self._begin_transaction())

    def tearDown(self):
        self._loop.run_until_complete(self._rollback_transaction())
        super().tearDown()

    async def _begin_transaction(self):
        self._test_session = None
        self._test_conn = None
        self._session_token = None
        try:
            from buraq.core.db import SessionLocal, _current_session
            self._test_session = SessionLocal()
            self._test_conn = await self._test_session.__aenter__()
            await self._test_conn.begin_nested()
            self._session_token = _current_session.set(self._test_conn)
        except Exception:
            if self._test_session is not None:
                await self._test_session.__aexit__(None, None, None)
            self._test_session = None
            self._test_conn = None

    async def _rollback_transaction(self):
        try:
            if self._session_token is not None:
                from buraq.core.db import _current_session
                _current_session.reset(self._session_token)
            if self._test_conn is not None:
                await self._test_conn.rollback()
            if self._test_session is not None:
                await self._test_session.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            self._test_session = None
            self._test_conn = None
            self._session_token = None


class DiscoverRunner:
    """
    Test runner that discovers and runs tests using pytest.

    Acts as a thin wrapper around ``pytest`` so that tests can be discovered
    via the standard ``buraq test`` command without locking the project into
    a specific test layout.

    Usage::

        runner = DiscoverRunner(verbosity=2, failfast=True)
        failures = runner.run_tests(["tests/", "myapp/tests/"])

    ``run_tests()`` returns the number of failed test items (0 = all passed).
    """

    def __init__(
        self,
        *,
        verbosity: int = 1,
        failfast: bool = False,
        keepdb: bool = False,
    ):
        self.verbosity = verbosity
        self.failfast = failfast
        self.keepdb = keepdb

    def run_tests(self, test_labels: list[str] | None = None) -> int:
        import pytest

        args: list[str] = list(test_labels or [])

        if self.verbosity >= 2:
            args.append("-v")
        elif self.verbosity == 0:
            args.append("-q")

        if self.failfast:
            args.append("-x")

        return pytest.main(args)

    # ── Setup / teardown hooks for the database ───────────────────────────────

    def setup_databases(self) -> None:
        """Create test databases (no-op by default — pytest fixtures handle this)."""

    def teardown_databases(self) -> None:
        """Drop test databases (no-op by default — pytest fixtures handle this)."""

    def setup_test_environment(self) -> None:
        import os
        os.environ.setdefault("BURAQ_ENV", "test")

    def teardown_test_environment(self) -> None:
        pass


class LiveServerTestCase(TestCase):
    """
    TestCase that starts a real HTTP server on a random port for the duration of the test.

    Use for tests that need to make real HTTP requests (e.g. Selenium, requests).

    Usage::

        class MyE2ETest(LiveServerTestCase):
            async def test_homepage(self):
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(self.live_server_url)
                    assert resp.status_code == 200
    """

    port: int = 0
    host: str = "127.0.0.1"
    live_server_url: str = ""
    _server = None
    _server_task = None

    def setUp(self):
        super().setUp()
        self._loop.run_until_complete(self._start_server())

    def tearDown(self):
        self._loop.run_until_complete(self._stop_server())
        super().tearDown()

    async def _start_server(self):
        import socket

        import uvicorn

        try:
            from buraq.core.app import get_app
            app = get_app()
        except Exception:
            app = self.app

        if not app:
            return

        # Pick a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, 0))
            self.port = s.getsockname()[1]

        self.live_server_url = f"http://{self.host}:{self.port}"

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self._server = uvicorn.Server(config)
        import asyncio
        self._server_task = self._loop.create_task(self._server.serve())
        # Give the server a moment to start
        await asyncio.sleep(0.1)

    async def _stop_server(self):
        if self._server:
            self._server.should_exit = True
            if self._server_task:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(self._server_task, timeout=2.0)
        self._server = None
        self._server_task = None
