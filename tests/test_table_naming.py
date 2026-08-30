"""
A default table name should be English a reader recognises.

The rule was the model name plus "s", which produced categorys, boxs, classs
and addresss -- names that appear in every query, every error message and every
database console for the life of the project.
"""

import pytest

from buraq.orm.base import _to_table_name


@pytest.mark.parametrize(
    "model,table",
    [
        # Unchanged by the new rules.
        ("Product", "products"),
        ("Post", "posts"),
        ("Day", "days"),                  # vowel before the y
        ("PostComment", "post_comments"),
        # Endings that took "es".
        ("Address", "addresses"),
        ("Box", "boxes"),
        ("Class", "classes"),
        ("Dish", "dishes"),
        ("Branch", "branches"),
        # Consonant before a y takes "ies".
        ("Category", "categories"),
        ("Company", "companies"),
        ("Entry", "entries"),
    ],
)
def test_default_table_names(model, table):
    assert _to_table_name(model) == table
    assert _to_table_name(model, "shop") == f"shop_{table}"


def test_irregular_plurals_are_not_attempted():
    """A rule cannot reach these, and pretending otherwise would be worse.

    Meta.db_table is the answer for them, which is why it exists.
    """
    assert _to_table_name("Person") == "persons"     # not "people"
    assert _to_table_name("Child") == "childs"       # not "children"


def test_framework_tables_are_unaffected(monkeypatch):
    """The migrations Buraq ships name their tables, so those must not move."""
    for model, expected in [
        ("User", "buraq_users"),
        ("Group", "buraq_groups"),
        ("Permission", "buraq_permissions"),
        ("Session", "buraq_sessions"),
    ]:
        assert _to_table_name(model, "buraq") == expected
