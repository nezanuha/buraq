"""
`{{ csrf_input }}` has to render a field, not a function.

Both are Jinja environment globals, and a global is a value rather than
something a bare ``{{ name }}`` calls -- so the form every documentation page
shows rendered the function object, HTML-escaped, into the page:

    &lt;function _csrf_input at 0x0000014B973716C0&gt;

Every documented form, and every one a scaffolded app produced, therefore posted
without a token and was refused with 403.
"""

from buraq.core.templating import _CsrfValue


def test_it_renders_rather_than_repr_ing():
    value = _CsrfValue("req", lambda r: f"<input value={r}>")
    assert value.__html__() == "<input value=req>"
    assert "function" not in str(value)


def test_nothing_is_computed_until_it_is_rendered():
    """A page that asks for no token should not create one."""
    calls = []
    value = _CsrfValue("req", lambda r: calls.append(r) or "x")
    assert calls == []
    value.__html__()
    assert calls == ["req"]


def test_calling_it_still_works():
    """Anything already written as csrf_input(request) must keep working."""
    value = _CsrfValue("bound", lambda r: f"for {r}")
    assert value() == "for bound"
    assert value("other") == "for other"


def test_render_supplies_it(monkeypatch):
    """It comes from render(), so a template gets it without asking."""
    import asyncio

    from buraq import shortcuts

    captured = {}

    class _Templates:
        def TemplateResponse(self, request, name, ctx):
            captured.update(ctx)
            return "rendered"

    monkeypatch.setattr(shortcuts, "get_templates", lambda: _Templates(), raising=False)
    monkeypatch.setattr(
        "buraq.core.templating.get_templates", lambda: _Templates(), raising=False
    )
    monkeypatch.setattr(
        "buraq.template.context_processors.run_context_processors",
        lambda req: _done({}),
    )

    asyncio.run(shortcuts.render(object(), "x.html", {"posts": []}))
    assert "csrf_input" in captured
    assert "csrf_token" in captured
    assert captured["posts"] == []


def test_a_caller_can_override_it(monkeypatch):
    """setdefault, not assignment -- a caller's own value wins."""
    import asyncio

    from buraq import shortcuts

    captured = {}

    class _Templates:
        def TemplateResponse(self, request, name, ctx):
            captured.update(ctx)
            return "rendered"

    monkeypatch.setattr(
        "buraq.core.templating.get_templates", lambda: _Templates(), raising=False
    )
    monkeypatch.setattr(
        "buraq.template.context_processors.run_context_processors",
        lambda req: _done({}),
    )

    asyncio.run(shortcuts.render(object(), "x.html", {"csrf_input": "mine"}))
    assert captured["csrf_input"] == "mine"


async def _done(value):
    return value
