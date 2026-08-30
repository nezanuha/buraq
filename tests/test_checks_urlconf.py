"""
`buraq check` must notice that the URLconf cannot be imported.

It is the command you run to find problems before starting the server, and it
reported a clean project while runserver died on the first line of
config/urls.py. A missing package, a typo in an import, a view that was renamed
-- the likeliest ways a project breaks, and the one command meant to catch them
did not look.
"""

from buraq.checks.urls import check_root_urlconf_imports


class _Settings:
    def __init__(self, root_urlconf):
        self.ROOT_URLCONF = root_urlconf


def test_a_urlconf_that_cannot_import_is_an_error():
    errors = check_root_urlconf_imports(_Settings("no_such_module_anywhere"))
    assert len(errors) == 1
    assert errors[0].id == "urls.E001"
    assert "no_such_module_anywhere" in errors[0].msg


def test_the_message_names_what_was_missing(tmp_path, monkeypatch):
    """The reader needs the package name, not just "could not be imported"."""
    (tmp_path / "brokenurls.py").write_text("import definitely_not_a_real_package\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    errors = check_root_urlconf_imports(_Settings("brokenurls"))
    assert len(errors) == 1
    assert "definitely_not_a_real_package" in errors[0].msg


def test_an_error_raised_on_import_is_reported_too(tmp_path, monkeypatch):
    """Not only ImportError -- anything raised means the project will not start."""
    (tmp_path / "raisingurls.py").write_text("raise ValueError('bad setting')\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    errors = check_root_urlconf_imports(_Settings("raisingurls"))
    assert len(errors) == 1
    assert errors[0].id == "urls.E002"
    assert "ValueError" in errors[0].msg


def test_a_urlconf_that_imports_is_no_error(tmp_path, monkeypatch):
    (tmp_path / "goodurls.py").write_text("urlpatterns = []\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    assert check_root_urlconf_imports(_Settings("goodurls")) == []


def test_no_root_urlconf_is_not_an_error():
    """A project may route entirely in main.py; that is not this check's business."""
    assert check_root_urlconf_imports(_Settings(None)) == []


def test_the_check_is_registered():
    """It has to run as part of `buraq check`, not only when called directly."""
    import buraq.checks  # noqa: F401  -- importing is what registers them
    from buraq.checks.registry import registry

    names = [getattr(fn, "__name__", "") for fn in registry._checks]
    assert "check_root_urlconf_imports" in names
