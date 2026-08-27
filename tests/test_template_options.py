"""TEMPLATE_OPTIONS reaches the Jinja environment.

Starlette builds a default environment and offers no way to alter it, so
``undefined``, ``trim_blocks`` and the extension list were unreachable.
"""

import jinja2
import pytest


@pytest.fixture
def render(tmp_path, monkeypatch):
    def _render(source: str, options: dict | None = None, **ctx):
        import buraq.core.templating as templating
        from buraq.conf import settings

        (tmp_path / "t.html").write_text(source, encoding="utf-8")
        monkeypatch.setattr(settings, "TEMPLATES_DIR", str(tmp_path), raising=False)
        monkeypatch.setattr(settings, "INSTALLED_APPS", [], raising=False)
        monkeypatch.setattr(settings, "TEMPLATE_OPTIONS", options or {}, raising=False)
        monkeypatch.setattr(templating, "_templates", None, raising=False)
        return templating.get_templates().get_template("t.html").render(**ctx)

    return _render


def test_undefined_is_configurable(render):
    """A typo renders as nothing by default; StrictUndefined makes it an error."""
    assert render("[{{ nope }}]") == "[]"

    with pytest.raises(jinja2.UndefinedError):
        render("[{{ nope }}]", {"undefined": jinja2.StrictUndefined})


def test_undefined_accepts_a_dotted_path(render):
    """A settings file should not have to import jinja2 to name a class."""
    with pytest.raises(jinja2.UndefinedError):
        render("[{{ nope }}]", {"undefined": "jinja2.StrictUndefined"})


def test_a_bad_dotted_path_is_reported(render):
    from buraq.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured, match="could not be imported"):
        render("hi", {"undefined": "nope.NotAThing"})


def test_string_options_are_left_alone(render):
    """block_start_string is legitimately a string; it must not be imported."""
    rendered = render(
        "<% if x %>{{ x }}<% endif %>",
        {"block_start_string": "<%", "block_end_string": "%>"},
        x="ok",
    )
    assert rendered == "ok"


def test_an_extension_can_be_added(render):
    """`{% break %}` needs jinja2.ext.loopcontrols, which nothing could load."""
    source = "{% for i in [1,2,3] %}{% if i == 2 %}{% break %}{% endif %}{{ i }}{% endfor %}"

    with pytest.raises(jinja2.TemplateSyntaxError):
        render(source)

    assert render(source, {"extensions": ["jinja2.ext.loopcontrols"]}) == "1"


def test_autoescape_survives_custom_options(render):
    """
    The one option that must not be lost by accident: without autoescape every
    variable interpolated into a page is a cross-site scripting hole.
    """
    escaped = "&lt;script&gt;"
    assert render("{{ evil }}", evil="<script>") == escaped
    assert render("{{ evil }}", {"trim_blocks": True}, evil="<script>") == escaped
