"""PostgreSQL-specific SQL functions for use in expressions and annotations."""
from __future__ import annotations

import sqlalchemy as sa


def Unaccent(field: str):
    """
    Remove accents — requires the unaccent extension.

    CREATE EXTENSION IF NOT EXISTS unaccent;

    Usage:
        Post.objects.annotate_expr(clean_title=Unaccent("title"))
    """
    def _build(model):
        return sa.func.unaccent(getattr(model, field))
    return _build


def Now():
    """Current timestamp with timezone (PostgreSQL NOW())."""
    return sa.func.now()


def Random():
    """Random float between 0 and 1 (PostgreSQL RANDOM())."""
    return sa.func.random()
