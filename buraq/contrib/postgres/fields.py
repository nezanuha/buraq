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

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY, HSTORE, JSONB


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
