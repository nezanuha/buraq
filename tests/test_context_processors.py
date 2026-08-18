"""
Tests for template context processors.

Regression context: `render()` used to be synchronous while
`run_context_processors()` is a coroutine, so the coroutine was never awaited
and the resulting TypeError was swallowed by a bare `except Exception: pass`.
TEMPLATE_CONTEXT_PROCESSORS silently did nothing at all.

`render()` is now a coroutine, which also lets a processor await the database --
every query in Buraq is async, so a sync-only processor could never do one.
"""

import contextlib

import pytest

from buraq.template.context_processors import run_context_processors


class FakeRequest:
    user = "alice"

    class state:
        language = "fr"


@pytest.fixture
def processors():
    from buraq.conf import settings

    original = getattr(settings, "TEMPLATE_CONTEXT_PROCESSORS", None)
    yield lambda paths: setattr(settings, "TEMPLATE_CONTEXT_PROCESSORS", paths)
    settings.TEMPLATE_CONTEXT_PROCESSORS = original


async def test_sync_processors_populate_the_context(processors):
    processors([
        "buraq.template.context_processors.request",
        "buraq.template.context_processors.auth",
        "buraq.template.context_processors.i18n",
    ])

    ctx = await run_context_processors(FakeRequest())

    assert ctx["user"] == "alice"
    assert ctx["LANGUAGE_CODE"] == "fr"
    assert "request" in ctx


async def test_async_processors_are_awaited(processors):
    """The whole point of an async render(): a processor can do I/O."""
    processors(["tests.test_context_processors.an_async_processor"])

    ctx = await run_context_processors(FakeRequest())

    assert ctx == {"unread_count": 7}


async def an_async_processor(req) -> dict:
    """Stands in for a processor that awaits the database."""
    import asyncio

    await asyncio.sleep(0)
    return {"unread_count": 7}


async def test_sync_and_async_processors_can_be_mixed(processors):
    processors([
        "buraq.template.context_processors.auth",
        "tests.test_context_processors.an_async_processor",
    ])

    ctx = await run_context_processors(FakeRequest())

    assert ctx["user"] == "alice"
    assert ctx["unread_count"] == 7


async def test_render_surfaces_processor_failure_instead_of_silence(processors, caplog):
    """A broken processor must be logged, not swallowed without trace."""
    processors(["tests.test_context_processors.broken_processor"])

    from buraq.shortcuts import render

    # Template lookup fails here; the assertion below is about the log.
    with caplog.at_level("ERROR"), contextlib.suppress(Exception):
        await render(FakeRequest(), "does-not-matter.html", {})

    assert any("context processors failed" in r.message for r in caplog.records)


def broken_processor(req) -> dict:
    raise ValueError("boom")


def test_render_is_a_coroutine_function():
    """Guards against silently reverting to a sync render()."""
    import inspect

    from buraq.shortcuts import render

    assert inspect.iscoroutinefunction(render)
