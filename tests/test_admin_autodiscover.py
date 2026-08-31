"""
An app with no admin.py is skipped; a broken one is not.

autodiscover() suppressed ModuleNotFoundError around the import, which covers
both cases -- so one typo'd import inside an app's admin.py meant its models
quietly never appeared in the admin, with nothing raised and nothing logged.
The two look identical from the outside: no models, no explanation.
"""

import sys

import pytest

from buraq.conf import settings
from buraq.contrib.admin import AdminSite


def _app(tmp_path, name, admin_source=None):
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "models.py").write_text("VALUE = 1\n")
    if admin_source is not None:
        (package / "admin.py").write_text(admin_source)
    return name


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))

    def use(*names):
        for name in names:
            sys.modules.pop(name, None)
            sys.modules.pop(f"{name}.admin", None)
        monkeypatch.setattr(settings, "INSTALLED_APPS", list(names), raising=False)

    return use


def test_an_app_without_admin_py_is_skipped(tmp_path, installed):
    installed(_app(tmp_path, "noadmin"))
    AdminSite().autodiscover()      # must not raise


def test_a_working_admin_py_is_imported(tmp_path, installed):
    name = _app(tmp_path, "goodadmin", "MARKER = True\n")
    installed(name)

    AdminSite().autodiscover()
    assert sys.modules[f"{name}.admin"].MARKER is True


def test_a_broken_import_inside_admin_py_is_raised(tmp_path, installed):
    """This was silent, and the models simply never showed up."""
    name = _app(tmp_path, "brokenadmin", "from .modelz import Thing\n")
    installed(name)

    with pytest.raises(ModuleNotFoundError, match="modelz"):
        AdminSite().autodiscover()


def test_any_other_error_inside_admin_py_is_raised(tmp_path, installed):
    name = _app(tmp_path, "raisingadmin", "raise ValueError('bad admin')\n")
    installed(name)

    with pytest.raises(ValueError, match="bad admin"):
        AdminSite().autodiscover()


def test_an_app_that_does_not_exist_does_not_stop_discovery(tmp_path, installed):
    """INSTALLED_APPS validation reports that; this loop should carry on."""
    good = _app(tmp_path, "afteradmin", "MARKER = True\n")
    installed("no_such_app_at_all", good)

    AdminSite().autodiscover()
    assert sys.modules[f"{good}.admin"].MARKER is True
