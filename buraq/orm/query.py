"""
Q objects and F expressions — complex ORM query building.

Usage:
    from buraq.orm.query import Q, F

    # Q objects
    await Post.objects.filter(Q(title__contains="hello") | Q(published=True))
    await Post.objects.filter(Q(author_id=1) & ~Q(status="draft"))

    # F expressions
    await Post.objects.filter(views__gt=F("likes"))
"""
import operator as _op

import sqlalchemy as sa


class F:
    """
    Reference a model field by name in a query expression.

    Usage:
        Post.objects.filter(views__gt=F("likes"))
        Post.objects.filter(score=F("views") + F("likes"))
    """

    def __init__(self, field_name: str):
        self.field_name = field_name
        self._expression = None  # set when arithmetic is applied

    def resolve(self, model):
        if self._expression is not None:
            return self._expression
        return getattr(model, self.field_name)

    def _make_expr(self, other, op):
        f = F(self.field_name)
        f._expression = (self, op, other)
        return f

    def __add__(self, other): return _FExpr(self, "+", other)
    def __sub__(self, other): return _FExpr(self, "-", other)
    def __mul__(self, other): return _FExpr(self, "*", other)
    def __truediv__(self, other): return _FExpr(self, "/", other)
    def __radd__(self, other): return _FExpr(other, "+", self)
    def __rsub__(self, other): return _FExpr(other, "-", self)


class _FExpr:
    """Arithmetic expression on F objects."""

    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def resolve(self, model):
        left = self.left.resolve(model) if isinstance(self.left, (F, _FExpr)) else self.left
        right = self.right.resolve(model) if isinstance(self.right, (F, _FExpr)) else self.right
        ops = {"+": _op.add, "-": _op.sub, "*": _op.mul, "/": _op.truediv}
        return ops[self.op](left, right)


class Q:
    """
    Encapsulate query conditions — supports & (AND), | (OR), ~ (NOT).

    Usage:
        Q(title="hello")
        Q(title__contains="hi") | Q(published=True)
        ~Q(status="draft")
        Q(author_id=1) & Q(published=True)
    """

    AND = "AND"
    OR = "OR"
    XOR = "XOR"

    def __init__(self, _connector=AND, _negated=False, **kwargs):
        self.connector = _connector
        self.negated = _negated
        self.children = list(kwargs.items())  # list of (key, value) or Q children

    def _combine(self, other, connector):
        q = Q(_connector=connector)
        q.children = [self, other]
        return q

    def __and__(self, other): return self._combine(other, Q.AND)
    def __or__(self, other): return self._combine(other, Q.OR)
    def __xor__(self, other): return self._combine(other, Q.XOR)
    def __invert__(self):
        q = Q(_connector=self.connector, _negated=not self.negated)
        q.children = list(self.children)
        return q

    def resolve(self, model) -> sa.sql.ClauseElement:
        """Convert this Q tree to a SQLAlchemy clause."""
        clauses = []
        for child in self.children:
            if isinstance(child, Q):
                clauses.append(child.resolve(model))
            else:
                key, value = child
                clauses.append(_resolve_lookup(model, key, value))

        if not clauses:
            return sa.true()

        if self.connector == Q.AND:
            clause = sa.and_(*clauses)
        elif self.connector == Q.XOR:
            clause = sa.and_(sa.or_(*clauses), sa.not_(sa.and_(*clauses)))
        else:
            clause = sa.or_(*clauses)

        return sa.not_(clause) if self.negated else clause


def _escape_like(value: str, escape_char: str = "\\") -> str:
    """Escape LIKE wildcards in a user-supplied string so they match literally."""
    return (
        value
        .replace(escape_char, escape_char * 2)
        .replace("%", escape_char + "%")
        .replace("_", escape_char + "_")
    )


def _resolve_lookup(model, key: str, value) -> sa.sql.ClauseElement:
    """Turn a filter kwarg into a SQLAlchemy clause (same logic as QuerySet.filter)."""
    _OPS = {
        "contains":    lambda c, v: c.contains(v),
        "icontains":   lambda c, v: c.ilike(f"%{_escape_like(v)}%", escape="\\"),
        "startswith":  lambda c, v: c.startswith(v),
        "istartswith": lambda c, v: c.ilike(f"{_escape_like(v)}%", escape="\\"),
        "endswith":    lambda c, v: c.endswith(v),
        "iendswith":   lambda c, v: c.ilike(f"%{_escape_like(v)}", escape="\\"),
        "exact":      lambda c, v: c == v,
        "iexact":     lambda c, v: c.ilike(v),
        "gt":         lambda c, v: c > v,
        "gte":        lambda c, v: c >= v,
        "lt":         lambda c, v: c < v,
        "lte":        lambda c, v: c <= v,
        "in":         lambda c, v: c.in_(v),
        "isnull":     lambda c, v: c.is_(None) if v else c.isnot(None),
        "range":      lambda c, v: c.between(v[0], v[1]),
        "year":       lambda c, v: sa.extract("year", c) == v,
        "month":      lambda c, v: sa.extract("month", c) == v,
        "day":        lambda c, v: sa.extract("day", c) == v,
    }
    if "__" in key:
        field_name, op = key.rsplit("__", 1)
        col = getattr(model, field_name)
        if isinstance(value, F):
            value = value.resolve(model)
        resolver = _OPS.get(op, lambda c, v: c == v)
        return resolver(col, value)
    else:
        col = getattr(model, key)
        if isinstance(value, F):
            value = value.resolve(model)
        return col == value
