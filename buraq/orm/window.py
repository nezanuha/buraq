"""
Window functions — RowNumber, Rank, DenseRank, Lag, Lead, etc.

Usage:
    from buraq.orm.window import Window, RowNumber, Rank, Lag

    qs = await Post.objects.annotate(
        row_num=Window(RowNumber(), partition_by="author_id", order_by="-created_at")
    )
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import func


class _WindowFunc:
    def sa_func(self) -> sa.sql.ColumnElement:
        raise NotImplementedError


class RowNumber(_WindowFunc):
    def sa_func(self): return func.row_number()


class Rank(_WindowFunc):
    def sa_func(self): return func.rank()


class DenseRank(_WindowFunc):
    def sa_func(self): return func.dense_rank()


class PercentRank(_WindowFunc):
    def sa_func(self): return func.percent_rank()


class CumeDist(_WindowFunc):
    def sa_func(self): return func.cume_dist()


class Ntile(_WindowFunc):
    def __init__(self, num_buckets: int):
        self.num_buckets = num_buckets

    def sa_func(self): return func.ntile(self.num_buckets)


class Lag(_WindowFunc):
    def __init__(self, field: str, offset: int = 1, default=None):
        self.field = field
        self.offset = offset
        self.default = default

    def sa_func(self): return None  # resolved in Window.resolve

    def resolve_expr(self, model):
        col = getattr(model, self.field)
        args = [col, self.offset]
        if self.default is not None:
            args.append(sa.literal(self.default))
        return func.lag(*args)


class Lead(_WindowFunc):
    def __init__(self, field: str, offset: int = 1, default=None):
        self.field = field
        self.offset = offset
        self.default = default

    def sa_func(self): return None

    def resolve_expr(self, model):
        col = getattr(model, self.field)
        args = [col, self.offset]
        if self.default is not None:
            args.append(sa.literal(self.default))
        return func.lead(*args)


class FirstValue(_WindowFunc):
    def __init__(self, field: str):
        self.field = field

    def sa_func(self): return None

    def resolve_expr(self, model):
        return func.first_value(getattr(model, self.field))


class LastValue(_WindowFunc):
    def __init__(self, field: str):
        self.field = field

    def sa_func(self): return None

    def resolve_expr(self, model):
        return func.last_value(getattr(model, self.field))


class NthValue(_WindowFunc):
    def __init__(self, field: str, nth: int):
        self.field = field
        self.nth = nth

    def sa_func(self): return None

    def resolve_expr(self, model):
        return func.nth_value(getattr(model, self.field), self.nth)


class Window:
    """
    Wrap a window function with OVER(PARTITION BY ... ORDER BY ...).

    Usage:
        Window(RowNumber(), partition_by="author_id", order_by="-created_at")
        Window(Rank(), order_by=["score", "-created_at"])
    """

    def __init__(self, expression: _WindowFunc, partition_by=None, order_by=None):
        self.expression = expression
        self.partition_by = partition_by
        self.order_by = order_by

    def _resolve_col(self, model, field: str):
        if field.startswith("-"):
            return getattr(model, field[1:]).desc()
        return getattr(model, field)

    def resolve(self, model) -> sa.sql.ColumnElement:
        expr = self.expression

        base = expr.resolve_expr(model) if hasattr(expr, "resolve_expr") else expr.sa_func()

        partition = None
        if self.partition_by:
            parts = [self.partition_by] if isinstance(self.partition_by, str) else self.partition_by
            partition = [getattr(model, p) for p in parts]

        order = None
        if self.order_by:
            fields = [self.order_by] if isinstance(self.order_by, str) else self.order_by
            order = [self._resolve_col(model, f) for f in fields]

        return base.over(partition_by=partition, order_by=order)


__all__ = [
    "Window",
    "RowNumber", "Rank", "DenseRank", "PercentRank", "CumeDist", "Ntile",
    "Lag", "Lead", "FirstValue", "LastValue", "NthValue",
]
