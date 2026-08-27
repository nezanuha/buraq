"""
`buraq.template.register` — globals and filters that need the render context.

Regression: `Library.global_`/`Library.filter` had no `takes_context` option,
so a helper needing the current request (`canonical_url()`, a language
switcher, anything context-processor-shaped) had no way to receive it —
Jinja2 globals and filters are called with only the arguments the template
passes.
"""

import jinja2
import pytest

from buraq.template.registry import Library


@pytest.fixture
def library():
    return Library()


def test_global_without_takes_context_is_unaffected(library):
    @library.global_
    def shout(value):
        return value.upper()

    env = jinja2.Environment()
    library.apply(env)
    assert env.from_string("{{ shout('hi') }}").render() == "HI"


def test_global_takes_context_receives_the_render_context(library):
    @library.global_(takes_context=True)
    def site_url(context):
        return context.get("SITE_FULL_URL", "")

    env = jinja2.Environment()
    library.apply(env)
    out = env.from_string("{{ site_url() }}").render(SITE_FULL_URL="https://x.test")
    assert out == "https://x.test"


def test_filter_takes_context_receives_context_ahead_of_the_piped_value(library):
    @library.filter(takes_context=True)
    def with_suffix(context, value):
        return f"{value}-{context.get('suffix', '')}"

    env = jinja2.Environment()
    library.apply(env)
    out = env.from_string("{{ name|with_suffix }}").render(name="post", suffix="v2")
    assert out == "post-v2"


def test_global_takes_context_combines_with_is_safe(library):
    @library.global_(takes_context=True, is_safe=True)
    def raw_badge(context):
        return f"<b>{context.get('label', '')}</b>"

    env = jinja2.Environment(autoescape=True)
    library.apply(env)
    out = env.from_string("{{ raw_badge() }}").render(label="new")
    assert out == "<b>new</b>"  # not escaped, despite autoescape=True


def test_explicit_name_still_works_with_takes_context(library):
    @library.global_(name="site_home", takes_context=True)
    def _home(context):
        return context.get("SITE_FULL_URL", "")

    env = jinja2.Environment()
    library.apply(env)
    out = env.from_string("{{ site_home() }}").render(SITE_FULL_URL="https://x.test")
    assert out == "https://x.test"


def test_templates_dir_takes_several_roots(tmp_path, monkeypatch):
    """
    A project with a shared theme beside its own templates has two roots, and a
    single string could only ever name one of them.
    """
    import buraq.core.templating as templating
    from buraq.conf import settings

    first, second = tmp_path / "a", tmp_path / "b"
    for d in (first, second):
        d.mkdir()
    (second / "only_here.html").write_text("second root", encoding="utf-8")

    monkeypatch.setattr(settings, "TEMPLATES_DIR", [str(first), str(second)], raising=False)
    monkeypatch.setattr(settings, "INSTALLED_APPS", [], raising=False)
    monkeypatch.setattr(templating, "_templates", None, raising=False)

    found = templating._collect_template_dirs()

    assert str(first) in found
    assert str(second) in found
    assert templating.get_templates().get_template("only_here.html").render() == "second root"
