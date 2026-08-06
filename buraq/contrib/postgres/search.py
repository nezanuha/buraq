"""
PostgreSQL full-text search for Buraq QuerySets.

Usage:
    from buraq.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

    # Filter by full-text search on a single field
    posts = await Post.objects.filter(SearchQuery("async python", field="body")).all()

    # Annotate with relevance rank and sort
    posts = await (
        Post.objects
        .annotate_expr(rank=SearchRank("body", "async python"))
        .order_by("-rank")
        .all()
    )

    # Search across multiple fields (combined tsvector)
    posts = await Post.objects.filter(
        SearchQuery("buraq", field="title", config="english")
    ).all()
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import REGCONFIG


def SearchVector(*fields: str, config: str = "english"):
    """
    Build a combined tsvector from multiple model fields.

    Returns a callable that resolves to a SQLAlchemy expression given a model class.
    Pass the result to annotate_expr():

        Post.objects.annotate_expr(search=SearchVector("title", "body"))
    """
    def _build(model):
        parts = [
            sa.func.to_tsvector(
                sa.cast(config, REGCONFIG),
                sa.cast(getattr(model, f), sa.Text),
            )
            for f in fields
        ]
        vec = parts[0]
        for p in parts[1:]:
            vec = vec.op("||")(p)
        return vec
    return _build


class SearchQuery:
    """
    Full-text search filter — use inside QuerySet.filter().

    Builds a WHERE tsvector @@ tsquery clause against a single field.
    Accepts plainto_tsquery (phrase-safe, no operators needed from the user).
    """

    def __init__(self, query: str, *, field: str, config: str = "english"):
        self._query = query
        self._field = field
        self._config = config

    def resolve(self, model):
        vec = sa.func.to_tsvector(
            sa.cast(self._config, REGCONFIG),
            sa.cast(getattr(model, self._field), sa.Text),
        )
        tsq = sa.func.plainto_tsquery(sa.cast(self._config, REGCONFIG), self._query)
        return vec.op("@@")(tsq)


def SearchRank(field: str, query: str, *, config: str = "english"):
    """
    Relevance score expression for use with annotate_expr().

    Returns a ts_rank SQLAlchemy expression (float 0–1).

    Usage:
        Post.objects.annotate_expr(rank=SearchRank("body", "hello world"))
    """
    def _build(model):
        vec = sa.func.to_tsvector(
            sa.cast(config, REGCONFIG),
            sa.cast(getattr(model, field), sa.Text),
        )
        tsq = sa.func.plainto_tsquery(sa.cast(config, REGCONFIG), query)
        return sa.func.ts_rank(vec, tsq)
    return _build
