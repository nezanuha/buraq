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


class BoolAnd:
    """True if all input values are true, otherwise false."""

    def __init__(self, field: str):
        self.field = field

    def resolve(self, model):
        return sa.func.bool_and(getattr(model, self.field))


class BoolOr:
    """True if at least one input value is true, otherwise false."""

    def __init__(self, field: str):
        self.field = field

    def resolve(self, model):
        return sa.func.bool_or(getattr(model, self.field))


class _TwoFieldAggregate:
    """Base for aggregates over two numeric columns."""

    _func_name: str = ""

    def __init__(self, y_field: str, x_field: str):
        self.y_field = y_field
        self.x_field = x_field

    def resolve(self, model):
        y = getattr(model, self.y_field)
        x = getattr(model, self.x_field)
        return getattr(sa.func, self._func_name)(y, x)


class Corr(_TwoFieldAggregate):
    """Pearson correlation coefficient of (y_field, x_field)."""
    _func_name = "corr"


class CovarPop(_TwoFieldAggregate):
    """Population covariance of (y_field, x_field)."""
    _func_name = "covar_pop"


class CovarSamp(_TwoFieldAggregate):
    """Sample covariance of (y_field, x_field)."""
    _func_name = "covar_samp"


class RegrAvgX(_TwoFieldAggregate):
    """Average of the independent variable (x)."""
    _func_name = "regr_avgx"


class RegrAvgY(_TwoFieldAggregate):
    """Average of the dependent variable (y)."""
    _func_name = "regr_avgy"


class RegrCount(_TwoFieldAggregate):
    """Number of rows where both inputs are non-null."""
    _func_name = "regr_count"


class RegrIntercept(_TwoFieldAggregate):
    """Y-intercept of the least-squares-fit linear equation."""
    _func_name = "regr_intercept"


class RegrR2(_TwoFieldAggregate):
    """Square of the correlation coefficient (R²)."""
    _func_name = "regr_r2"


class RegrSlope(_TwoFieldAggregate):
    """Slope of the least-squares-fit linear equation."""
    _func_name = "regr_slope"


class RegrSXX(_TwoFieldAggregate):
    """Sum of squares of the independent variable."""
    _func_name = "regr_sxx"


class RegrSXY(_TwoFieldAggregate):
    """Sum of products of independent times dependent variable."""
    _func_name = "regr_sxy"


class RegrSYY(_TwoFieldAggregate):
    """Sum of squares of the dependent variable."""
    _func_name = "regr_syy"
