"""
ORM expressions — Case/When, Subquery, Exists, OuterRef, ExpressionWrapper.

Usage:
    from buraq.orm.expressions import Case, When, Value, OuterRef, Subquery, Exists

    # Conditional expression
    qs = await Post.objects.annotate(
        status_label=Case(
            When(status="published", then=Value("Live")),
            When(status="draft",     then=Value("Draft")),
            default=Value("Unknown"),
        )
    )

    # Correlated subquery
    comment_count = Subquery(
        Comment.objects.filter(post_id=OuterRef("id")).values("id").annotate(n=Count("id"))
        .values("n")
    )
    await Post.objects.annotate(comment_count=comment_count)

    # EXISTS subquery
    has_comments = Exists(Comment.objects.filter(post_id=OuterRef("id")))
    await Post.objects.filter(has_comments=has_comments)
"""
from __future__ import annotations

from typing import Any

import sqlalchemy as sa


class Value:
    """Wrap a literal Python value for use in expressions."""

    def __init__(self, value: Any, output_field=None):
        self.value = value
        self.output_field = output_field

    def resolve(self, model) -> sa.sql.ColumnElement:
        return sa.literal(self.value)


class When:
    """A single branch in a Case expression."""

    def __init__(self, condition=None, then=None, **kwargs):
        self.condition = condition
        self.then = then
        self.kwargs = kwargs

    def resolve_condition(self, model) -> sa.sql.ColumnElement:
        if self.condition is not None:
            if hasattr(self.condition, "resolve"):
                return self.condition.resolve(model)
            return self.condition
        from buraq.orm.query import _resolve_lookup
        clauses = []
        for key, value in self.kwargs.items():
            clauses.append(_resolve_lookup(model, key, value))
        return sa.and_(*clauses)

    def resolve_then(self, model) -> sa.sql.ColumnElement:
        if hasattr(self.then, "resolve"):
            return self.then.resolve(model)
        return sa.literal(self.then)


class Case:
    """
    SQL CASE expression.

        Case(
            When(score__gte=90, then=Value("A")),
            When(score__gte=80, then=Value("B")),
            default=Value("C"),
        )
    """

    def __init__(self, *whens: When, default=None):
        self.whens = whens
        self.default = default

    def resolve(self, model) -> sa.sql.ColumnElement:
        cases = [
            (w.resolve_condition(model), w.resolve_then(model))
            for w in self.whens
        ]
        default = None
        if self.default is not None:
            if hasattr(self.default, "resolve"):
                default = self.default.resolve(model)
            else:
                default = sa.literal(self.default)
        return sa.case(*cases, else_=default)


class OuterRef:
    """
    Reference a field on the outer query inside a Subquery.

        Subquery(Comment.objects.filter(post_id=OuterRef("id")).values("author_id"))
    """

    def __init__(self, field: str):
        self.field = field

    def resolve(self, model):
        return getattr(model, self.field)


class Subquery:
    """
    Embed a QuerySet as a scalar subquery.

        comment_ids = Subquery(
            Comment.objects.filter(post_id=OuterRef("id")).values_list("id", flat=True)
        )
    """

    def __init__(self, queryset):
        self._queryset = queryset

    def resolve(self, outer_model) -> sa.sql.ColumnElement:
        inner_q = self._queryset._query
        inner_q = self._replace_outer_refs(inner_q, outer_model)
        return inner_q.scalar_subquery()

    def _replace_outer_refs(self, query, outer_model):
        """Walk the query tree and replace __outerref__<field> placeholders."""
        from buraq.orm.query import _OUTER_REF_PREFIX
        from sqlalchemy.sql import visitors
        from sqlalchemy.sql.elements import ColumnClause

        replacements: dict[str, sa.sql.ColumnElement] = {}

        def _collect(elem):
            if isinstance(elem, ColumnClause) and elem.key.startswith(_OUTER_REF_PREFIX):
                field_name = elem.key[len(_OUTER_REF_PREFIX):]
                replacements[elem.key] = getattr(outer_model, field_name)

        visitors.traverse(query, {}, {"column": _collect})

        if not replacements:
            return query

        def _replace(elem):
            if isinstance(elem, ColumnClause) and elem.key in replacements:
                return replacements[elem.key]
            return None

        return visitors.cloned_traverse(query, {}, {"column": _replace})


class Exists(Subquery):
    """
    EXISTS(...) subquery expression.

        has_comments = Exists(Comment.objects.filter(post_id=OuterRef("id")))
        await Post.objects.filter(has_comments=has_comments)
    """

    def resolve(self, outer_model) -> sa.sql.ColumnElement:
        inner_q = self._queryset._query
        inner_q = self._replace_outer_refs(inner_q, outer_model)
        return sa.exists(inner_q)


class ExpressionWrapper:
    """
    Wrap an arbitrary SQLAlchemy expression and assign it an output field type.

        ExpressionWrapper(F("price") * F("quantity"), output_field="numeric")
    """

    def __init__(self, expression, output_field=None):
        self.expression = expression
        self.output_field = output_field

    def resolve(self, model) -> sa.sql.ColumnElement:
        if hasattr(self.expression, "resolve"):
            return self.expression.resolve(model)
        return self.expression


__all__ = ["Value", "When", "Case", "OuterRef", "Subquery", "Exists", "ExpressionWrapper"]
