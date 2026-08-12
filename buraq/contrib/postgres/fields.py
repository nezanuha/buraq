"""
PostgreSQL-specific SQLAlchemy column types for Buraq models.

Usage:
    from sqlalchemy import Column
    from buraq.contrib.postgres.fields import JSONField, ArrayField, HStoreField

    class Article(Model):
        metadata = Column(JSONField, default=dict)
        tags = Column(ArrayField(Text), default=list)
        attributes = Column(HStoreField, default=dict)
"""
from __future__ import annotations

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    CITEXT,
    DATERANGE,
    HSTORE,
    INT4RANGE,
    INT8RANGE,
    JSONB,
    NUMRANGE,
    TSTZRANGE,
)


class JSONField(JSONB):
    """
    PostgreSQL JSONB column — binary JSON with GIN indexing support.

    Prefer over JSONField for any data you need to query or index.
    Stores arbitrary dicts, lists, and scalars.
    """


class ArrayField(ARRAY):
    """
    PostgreSQL ARRAY column.

    Usage:
        tags = Column(ArrayField(Text), default=list)
        scores = Column(ArrayField(Integer), default=list)
    """


class HStoreField(HSTORE):
    """
    PostgreSQL hstore column — flat key/value string pairs stored natively.

    Requires the hstore extension: CREATE EXTENSION IF NOT EXISTS hstore;
    """


# ── Case-insensitive text fields ──────────────────────────────────────────────

class CITextField(CITEXT):
    """Case-insensitive text (requires the citext extension)."""


class CICharField(CITEXT):
    """Case-insensitive varchar (stores as citext)."""


class CIEmailField(CITEXT):
    """Case-insensitive email field."""


# ── Range fields ──────────────────────────────────────────────────────────────

class IntegerRangeField(INT4RANGE):
    """PostgreSQL int4range."""


class BigIntegerRangeField(INT8RANGE):
    """PostgreSQL int8range."""


class DecimalRangeField(NUMRANGE):
    """PostgreSQL numrange."""


class DateRangeField(DATERANGE):
    """PostgreSQL daterange."""


class DateTimeRangeField(TSTZRANGE):
    """PostgreSQL tstzrange (with timezone)."""


# ── Advanced index types ──────────────────────────────────────────────────────

def GinIndex(name: str, *columns, **kwargs) -> Index:
    """
    PostgreSQL GIN index — ideal for JSONB, ARRAY, and full-text search.

    Usage::

        class Meta:
            indexes = [GinIndex("tags_gin_idx", "tags")]
    """
    return Index(name, *columns, postgresql_using="gin", **kwargs)


def GistIndex(name: str, *columns, **kwargs) -> Index:
    """
    PostgreSQL GiST index — ideal for geometric types, range types, and tsvector.

    Usage::

        class Meta:
            indexes = [GistIndex("location_gist_idx", "location")]
    """
    return Index(name, *columns, postgresql_using="gist", **kwargs)


def BrinIndex(name: str, *columns, pages_per_range: int = None, **kwargs) -> Index:
    """
    PostgreSQL BRIN index — very small, good for naturally ordered data.

    Usage::

        class Meta:
            indexes = [BrinIndex("created_brin_idx", "created_at")]
    """
    if pages_per_range:
        kwargs["postgresql_with"] = {"pages_per_range": pages_per_range}
    return Index(name, *columns, postgresql_using="brin", **kwargs)


def SpGistIndex(name: str, *columns, **kwargs) -> Index:
    """
    PostgreSQL SP-GiST index — space-partitioned GiST for non-balanced structures.
    """
    return Index(name, *columns, postgresql_using="spgist", **kwargs)


def BloomIndex(name: str, *columns, length: int = None, col_length: int = None, **kwargs) -> Index:
    """
    PostgreSQL Bloom index — probabilistic data structure for multi-column equality lookups.
    """
    with_opts = {}
    if length:
        with_opts["length"] = length
    if col_length:
        with_opts["col1"] = col_length
    if with_opts:
        kwargs["postgresql_with"] = with_opts
    return Index(name, *columns, postgresql_using="bloom", **kwargs)


def HashIndex(name: str, *columns, **kwargs) -> Index:
    """PostgreSQL hash index — O(1) equality lookups."""
    return Index(name, *columns, postgresql_using="hash", **kwargs)


def TrgmIndex(name: str, *columns, index_type: str = "gin", **kwargs) -> Index:
    """
    PostgreSQL trigram index using the pg_trgm extension.

    Enables fast ``LIKE``, ``ILIKE``, and similarity (``%``) queries on text columns.
    Requires ``CREATE EXTENSION IF NOT EXISTS pg_trgm;`` on the database.

    Args:
        name:        Index name.
        columns:     One or more text column names.
        index_type:  ``"gin"`` (default) or ``"gist"``.

    Usage::

        from buraq.contrib.postgres.fields import TrgmIndex

        class Meta:
            indexes = [TrgmIndex("title_trgm_idx", "title")]
            # GiST variant (better for similarity ORDER BY):
            indexes = [TrgmIndex("title_trgm_gist_idx", "title", index_type="gist")]
    """
    if index_type not in ("gin", "gist"):
        raise ValueError(f"TrgmIndex index_type must be 'gin' or 'gist', got {index_type!r}")
    return Index(
        name,
        *columns,
        postgresql_using=index_type,
        postgresql_ops={col: "gin_trgm_ops" if index_type == "gin" else "gist_trgm_ops"
                        for col in columns},
        **kwargs,
    )
