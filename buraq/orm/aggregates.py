"""
Aggregation functions — Count, Sum, Avg, Min, Max for use with aggregate() and annotate().

Usage:
    from buraq.orm.aggregates import Count, Sum, Avg, Min, Max

    result = await Post.objects.aggregate(total=Count("id"), avg=Avg("views"))
    # → {"total": 42, "avg": 7.3}

    qs = await Post.objects.values("author_id").annotate(post_count=Count("id"))
    # → [{"author_id": 1, "post_count": 5}, ...]
"""
import sqlalchemy as sa
from sqlalchemy import func


class Aggregate:
    """Base class for aggregate functions."""

    sa_func = None

    def __init__(self, field: str, distinct: bool = False, filter=None, default=None):
        self.field = field
        self.distinct = distinct
        self.filter = filter
        self.default = default

    def resolve(self, model) -> sa.sql.ColumnElement:
        col = getattr(model, self.field) if self.field != "*" else sa.literal_column("1")
        agg = self.sa_func(col.distinct() if self.distinct else col)
        if self.filter is not None:
            agg = agg.filter(self.filter.resolve(model))
        if self.default is not None:
            agg = func.coalesce(agg, sa.literal(self.default))
        return agg


class Count(Aggregate):
    sa_func = func.count

    def __init__(self, field="*", distinct=False, **kwargs):
        super().__init__(field, distinct, **kwargs)

    def resolve(self, model):
        col = sa.literal_column("1") if self.field == "*" else getattr(model, self.field)
        return func.count(col.distinct() if self.distinct else col)


class Sum(Aggregate):
    sa_func = func.sum


class Avg(Aggregate):
    sa_func = func.avg


class Min(Aggregate):
    sa_func = func.min


class Max(Aggregate):
    sa_func = func.max


class StdDev(Aggregate):
    sa_func = func.stddev


class Variance(Aggregate):
    sa_func = func.variance


class BitAnd(Aggregate):
    """Bitwise AND of all non-NULL integer values."""
    sa_func = func.bit_and


class BitOr(Aggregate):
    """Bitwise OR of all non-NULL integer values."""
    sa_func = func.bit_or


class BitXor(Aggregate):
    """Bitwise XOR of all non-NULL integer values."""
    sa_func = func.bit_xor


class AnyValue(Aggregate):
    """
    Return an arbitrary non-NULL value from the group.

    Useful in ``GROUP BY`` queries when a column is functionally dependent on
    the group key but is not itself in the ``GROUP BY`` clause.  Avoids the
    need to wrap the column in ``MAX()`` or ``MIN()`` when any value would do.

    Database support: MySQL 8.0.2+, Oracle, MariaDB 10.3+.
    PostgreSQL users should use ``Max`` or ``Min`` instead (no native
    ``any_value()`` until PostgreSQL 16).

    Usage::

        results = await Order.objects.values("customer_id").annotate(
            sample_note=AnyValue("note")
        )
    """
    sa_func = func.any_value
