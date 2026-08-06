"""
PostgreSQL-specific aggregate functions.

Use with QuerySet.aggregate() or QuerySet.annotate():

    from buraq.contrib.postgres.aggregates import ArrayAgg, StringAgg, JsonAgg

    result = await Post.objects.aggregate(all_tags=ArrayAgg("tag"))
    result = await Post.objects.values("author_id").annotate(titles=StringAgg("title", delimiter=", "))
"""
from __future__ import annotations

import sqlalchemy as sa


class ArrayAgg:
    """Aggregate column values into a PostgreSQL array."""

    def __init__(self, field: str, *, distinct: bool = False):
        self.field = field
        self.distinct = distinct

    def resolve(self, model):
        col = getattr(model, self.field)
        return sa.func.array_agg(sa.distinct(col) if self.distinct else col)


class StringAgg:
    """Concatenate string values with a delimiter."""

    def __init__(self, field: str, *, delimiter: str = ",", distinct: bool = False):
        self.field = field
        self.delimiter = delimiter
        self.distinct = distinct

    def resolve(self, model):
        col = getattr(model, self.field)
        return sa.func.string_agg(
            sa.distinct(col) if self.distinct else col,
            self.delimiter,
        )


class JsonAgg:
    """Aggregate rows into a JSON array."""

    def __init__(self, field: str, *, distinct: bool = False):
        self.field = field
        self.distinct = distinct

    def resolve(self, model):
        col = getattr(model, self.field)
        return sa.func.json_agg(sa.distinct(col) if self.distinct else col)


class BitAnd:
    """Bitwise AND across all non-null integer values."""

    def __init__(self, field: str):
        self.field = field

    def resolve(self, model):
        return sa.func.bit_and(getattr(model, self.field))


class BitOr:
    """Bitwise OR across all non-null integer values."""

    def __init__(self, field: str):
        self.field = field

    def resolve(self, model):
        return sa.func.bit_or(getattr(model, self.field))
