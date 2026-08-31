"""
`buraq startapp posts` should produce an app that runs.

It did not. An app name is conventionally plural, and the scaffold appended "s"
to it for every plural and capitalised it for the model, so `startapp posts`
gave a `Posts` model whose table came out `posts_postses`, a view called
`list_postss`, and templates under `postss/`. The templates it named were never
written, so every page answered TemplateNotFound, and `admin.py` imported a
decorator that does not exist.
"""

import subprocess
import sys

import pytest

from buraq.management.cli import _app_templates, _singularize
from buraq.orm.base import _pluralize


@pytest.mark.parametrize(
    "app,singular,plural",
    [
        ("posts", "post", "posts"),
        ("articles", "article", "articles"),
        ("categories", "category", "categories"),
        ("boxes", "box", "boxes"),
        ("classes", "class", "classes"),
        # Already singular -- left alone.
        ("blog", "blog", "blogs"),
    ],
)
def test_names_round_trip(app, singular, plural):
    assert _singularize(app) == singular
    assert _pluralize(_singularize(app)) == plural


def test_a_plural_app_name_is_not_pluralised_again():
    """`posts` gave list_postss and a posts_postses table."""
    assert _singularize("posts") == "post"
    assert _pluralize("post") == "posts"
    assert "ss" not in _pluralize(_singularize("posts"))


def _scaffold(tmp_path):
    """Run startapp in a real directory and return it."""
    subprocess.run(
        [sys.executable, "-m", "buraq", "startapp", "posts"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    return tmp_path / "posts"


def test_the_generated_files_are_all_written(tmp_path):
    app = _scaffold(tmp_path)
    for relative in (
        "models.py", "views.py", "urls.py", "admin.py", "schemas.py", "apps.py",
        "templates/posts/list.html", "templates/posts/create.html",
        "templates/posts/detail.html", "templates/posts/edit.html",
    ):
        assert (app / relative).exists(), f"startapp did not write {relative}"


def test_no_name_is_doubled(tmp_path):
    app = _scaffold(tmp_path)
    for path in app.rglob("*.py"):
        body = path.read_text(encoding="utf-8")
        assert "postss" not in body, f"{path.name} still doubles the app name"
        assert "class Posts(" not in body, f"{path.name} names the model in the plural"


def test_every_generated_module_imports(tmp_path):
    """admin.py used @admin.register, which did not exist, so nothing loaded."""
    _scaffold(tmp_path)
    for module in ("models", "views", "urls", "admin", "schemas"):
        result = subprocess.run(
            [sys.executable, "-c", f"import posts.{module}"],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert result.returncode == 0, f"posts.{module} does not import:\n{result.stderr}"


def test_routes_are_not_duplicated(tmp_path):
    """/new was two entries, one per method, under two different names."""
    urls = _scaffold(tmp_path).joinpath("urls.py").read_text(encoding="utf-8")
    assert urls.count("'/new'") == 1
    assert urls.count("'/<int:pk>/edit'") == 1
    assert "methods=['GET', 'POST']" in urls


def test_redirects_go_through_reverse(tmp_path):
    """A hardcoded path guesses where the project mounted the app."""
    views = _scaffold(tmp_path).joinpath("views.py").read_text(encoding="utf-8")
    assert "redirect(reverse('posts_list'))" in views
    assert "redirect('/" not in views


def test_the_templates_use_the_documented_csrf_form():
    """`{{ csrf_input }}` -- the form every documentation page shows."""
    templates = _app_templates("posts", "post", "posts")
    assert "{{ csrf_input }}" in templates["create.html"]
    assert "{{ csrf_input }}" in templates["edit.html"]


def test_schemas_py_says_what_it_is_for(tmp_path):
    """A generated file that needs a documentation page to explain it is a bug.

    schemas.py arrived holding two classes with nothing about what they were,
    when to write them, or that an app serving only HTML can delete the file.
    """
    schemas = _scaffold(tmp_path).joinpath("schemas.py").read_text(encoding="utf-8")

    assert schemas.startswith('"""'), "no module docstring"
    assert "JSON" in schemas
    assert "can delete this file" in schemas, "it should say when it is not needed"
    assert "docs/topics/schemas" in schemas, "and where the detail is"


def test_apps_py_is_written_and_optional(tmp_path):
    """The apps documentation says to create one; the scaffold did not.

    ready() was therefore reachable only by somebody who had read that page and
    knew the file was theirs to add.
    """
    apps = _scaffold(tmp_path).joinpath("apps.py").read_text(encoding="utf-8")

    assert "class PostConfig(AppConfig)" in apps
    assert "async def ready" in apps
    assert "Optional" in apps, "it should say the app works without it"
    assert "posts.apps.PostConfig" in apps, "and how to name it in INSTALLED_APPS"
