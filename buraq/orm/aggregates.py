"""
Aggregation functions — like Django's Count, Sum, Avg, Min, Max.

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

    def __init__(self, field: str, distinct: bool = False, filter=None):
        self.field = field
        self.distinct = distinct
        self.filter = filter

    def resolve(self, model) -> sa.sql.ColumnElement:
        col = getattr(model, self.field) if self.field != "*" else sa.literal_column("1")
        agg = self.sa_func(col.distinct() if self.distinct else col)
        if self.filter is not None:
            agg = agg.filter(self.filter.resolve(model))
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
