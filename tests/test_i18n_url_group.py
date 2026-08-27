"""
`i18n_patterns()` in a `urlpatterns` list.

Regression: `i18n_patterns()` returns an `I18nURLGroup` — a plain dataclass
with no `__iter__` — but its own docstring, and three examples across the
docs, showed spreading it with `*i18n_patterns(...)`. That raises
`TypeError: 'I18nURLGroup' object is not iterable`, and so does the `+=`
a project would reach for instead once the `*` form fails.
`register_urlpatterns()` special-cases an `I18nURLGroup` it finds as a plain
list *element* (`isinstance(item, I18nURLGroup)`), so that's the only form
that was ever going to work.
"""

import pytest
from fastapi import FastAPI

from buraq.urls import (
    I18nURLGroup,
    _i18n_prefix_default,
    _i18n_route_names,
    i18n_patterns,
    path,
    register_urlpatterns,
)


async def _view(request):
    return {"ok": True}


def test_i18n_patterns_result_is_not_iterable():
    """Documents why `*i18n_patterns(...)` and `list += i18n_patterns(...)` both fail."""
    group = i18n_patterns(path("/", _view, name="home"))
    with pytest.raises(TypeError):
        list(group)


def test_group_appended_to_urlpatterns_registers_and_records_i18n_state():
    name = "home_i18n_group_test"
    urlpatterns = [
        i18n_patterns(path("/i18n-group-test", _view, name=name), prefix_default_language=False),
    ]

    app = FastAPI()
    register_urlpatterns(app, urlpatterns)

    assert name in _i18n_route_names
    assert _i18n_prefix_default[name] is False
    assert any(getattr(r, "path", None) == "/i18n-group-test" for r in app.routes)


def test_group_included_via_list_literal_also_registers():
    """The corrected docs example: the group as one element among plain patterns."""
    name = "about_i18n_group_test"
    urlpatterns = [
        path("/set-language", _view),
        i18n_patterns(path("/i18n-group-test-2", _view, name=name)),
    ]

    app = FastAPI()
    register_urlpatterns(app, urlpatterns)

    assert name in _i18n_route_names
    assert isinstance(urlpatterns[1], I18nURLGroup)
