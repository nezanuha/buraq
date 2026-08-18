"""
Decorator import paths.

Decorators are importable two ways: the flat `buraq.decorators` namespace, and
per-concern modules. Both must resolve to the same objects.

Two of these were broken before: `buraq.contrib.auth.decorators` did not exist
(the homepage sample imported it), and `buraq.views.decorators.csp` did not
either (the migration guide documented it).
"""

import importlib

import pytest

DECORATOR_MODULES = [
    (
        "buraq.contrib.auth.decorators",
        ["login_required", "permission_required", "user_passes_test"],
    ),
    (
        "buraq.views.decorators.http",
        ["require_GET", "require_POST", "require_http_methods", "require_safe", "condition"],
    ),
    ("buraq.views.decorators.cache", ["cache_page", "never_cache", "cache_control"]),
    ("buraq.views.decorators.csrf", ["csrf_exempt", "csrf_protect", "ensure_csrf_cookie"]),
    ("buraq.views.decorators.vary", ["vary_on_headers", "vary_on_cookie"]),
    ("buraq.views.decorators.csp", ["csp_override", "csp_report_only_override"]),
]


@pytest.mark.parametrize("module_path,names", DECORATOR_MODULES)
def test_grouped_import_paths_resolve(module_path, names):
    module = importlib.import_module(module_path)
    missing = [n for n in names if not hasattr(module, n)]
    assert not missing, f"{module_path} is missing {missing}"


@pytest.mark.parametrize("module_path,names", DECORATOR_MODULES)
def test_exported_names_are_callable(module_path, names):
    module = importlib.import_module(module_path)
    for name in names:
        assert callable(getattr(module, name)), f"{module_path}.{name} is not callable"


def test_paths_are_aliases_not_copies():
    """Both import styles must yield the same object, not a divergent copy."""
    from buraq.contrib.auth.decorators import login_required as via_contrib
    from buraq.decorators import cache_page as cache_via_flat
    from buraq.decorators import login_required as via_flat
    from buraq.views.decorators.cache import cache_page as cache_via_pkg

    assert via_contrib is via_flat
    assert cache_via_pkg is cache_via_flat


def test_csp_decorators_still_importable_from_the_package_root():
    """`buraq.views.decorators` was a flat module before; that import must keep working."""
    from buraq.views.decorators import csp_override, csp_report_only_override
    from buraq.views.decorators.csp import csp_override as from_submodule

    assert csp_override is from_submodule
    assert callable(csp_report_only_override)
