"""
Buraq ships migrations for its own tables.

The framework defines ten tables across five contrib apps. With a single
migration history they landed in each project's own alembic/versions, so a
release that changed buraq.contrib.auth forced every project to autogenerate and
review a schema it does not own -- and Buraq could not ship a data migration at
all.

Each contrib app now owns an Alembic branch inside the installed package,
applied only when the app is in INSTALLED_APPS.
"""

import ast
from pathlib import Path

import pytest

from buraq.core.db import (
    APPS_WITH_MIGRATIONS,
    framework_table_names,
    migration_version_locations,
    tables_migrations_ignore,
)

PACKAGE = Path(__file__).resolve().parents[1] / "buraq"


def _revision(app: str) -> Path:
    return PACKAGE / "contrib" / app / "migrations" / "versions" / "0001_initial.py"


@pytest.mark.parametrize("app", APPS_WITH_MIGRATIONS)
def test_every_listed_app_ships_a_revision(app):
    assert _revision(app).is_file(), f"buraq.contrib.{app} is listed but ships no migration"


@pytest.mark.parametrize("app", APPS_WITH_MIGRATIONS)
def test_each_revision_declares_its_own_branch(app):
    """
    Without a distinct branch label the framework's revisions would chain onto
    whatever the project last generated, and installing an app later could not
    bring its tables with it.
    """
    tree = ast.parse(_revision(app).read_text(encoding="utf-8"))
    assigned = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }

    assert assigned["revision"] == f"buraq_{app}_0001"
    assert assigned["down_revision"] is None
    assert assigned["branch_labels"] == (f"buraq_{app}",)


@pytest.mark.parametrize("app", APPS_WITH_MIGRATIONS)
def test_each_revision_creates_tables(app):
    source = _revision(app).read_text(encoding="utf-8")

    assert "op.create_table(" in source


def test_framework_tables_are_excluded_from_project_autogeneration():
    """
    A project's makemigrations must not emit the framework's schema; the shipped
    branch already creates it.
    """
    import buraq.contrib.auth.models  # noqa: F401

    tables = framework_table_names()

    assert "buraq_users" in tables
    assert tables <= tables_migrations_ignore()


def test_only_contrib_tables_are_treated_as_the_frameworks():
    """
    The rule is ownership by module, so a project's own models -- whatever they
    are named -- keep being generated into the project's own history.
    """
    import buraq.contrib.auth.models  # noqa: F401
    from buraq.core.db import Base

    owners = {
        mapper.class_.__tablename__: mapper.class_.__module__
        for mapper in Base.registry.mappers
        if getattr(mapper.class_, "__tablename__", None)
    }

    for table in framework_table_names():
        assert owners[table].startswith("buraq.contrib."), table


def test_only_installed_apps_contribute_version_locations(monkeypatch):
    """An app that is not installed must not have its tables created."""
    from buraq.conf import settings

    monkeypatch.setattr(settings, "INSTALLED_APPS", ["buraq.contrib.auth", "shop"])

    locations = migration_version_locations()

    assert locations == ["buraq.contrib.auth:migrations/versions"]


def test_a_config_path_entry_still_counts(monkeypatch):
    from buraq.conf import settings

    monkeypatch.setattr(settings, "INSTALLED_APPS", ["buraq.contrib.auth.apps.AuthConfig"])

    assert migration_version_locations() == ["buraq.contrib.auth:migrations/versions"]


def test_no_apps_installed_yields_no_locations(monkeypatch):
    from buraq.conf import settings

    monkeypatch.setattr(settings, "INSTALLED_APPS", ["shop"])

    assert migration_version_locations() == []


def test_migrate_targets_every_branch():
    """
    `head` fails outright once more than one branch exists, and the framework's
    branches are heads too.
    """
    import inspect

    from buraq.management.cli import migrate

    default = inspect.signature(migrate).parameters["revision"].default

    assert default.default == "heads"
