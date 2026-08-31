"""
Everything about the database is reachable under `buraq.db`.

`buraq/db/__init__.py` re-exported the transaction module as an attribute, which
made `from buraq.db import transaction` work while
`from buraq.db.transaction import atomic` raised ModuleNotFoundError -- an
attribute is not a submodule. The documentation used the second form, so the
line it showed did not run.
"""

import importlib

import pytest

NAMES = ["atomic", "on_commit", "non_atomic", "TransactionManagementError"]


@pytest.mark.parametrize("name", NAMES)
def test_importable_from_the_submodule(name):
    module = importlib.import_module("buraq.db.transaction")
    assert hasattr(module, name)


def test_the_submodule_is_a_real_module():
    """import_module has to find it, not just attribute access on the package."""
    assert importlib.import_module("buraq.db.transaction") is not None


@pytest.mark.parametrize("name", ["atomic", "on_commit", "transaction"])
def test_still_importable_from_the_package(name):
    """The shorter form was there first and stays."""
    module = importlib.import_module("buraq.db")
    assert hasattr(module, name)


@pytest.mark.parametrize("name", NAMES)
def test_it_is_the_same_object_as_the_implementation(name):
    """A re-export, not a copy -- two atomics would be two context variables."""
    facade = importlib.import_module("buraq.db.transaction")
    real = importlib.import_module("buraq.orm.transaction")
    assert getattr(facade, name) is getattr(real, name)
