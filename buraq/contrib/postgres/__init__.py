"""
PostgreSQL-specific fields, aggregates, and full-text search for Buraq.

Requires asyncpg driver: DATABASE_URL = "postgresql+asyncpg://..."

Usage:
    from buraq.contrib.postgres.fields import ArrayField, JSONField, HStoreField
    from buraq.contrib.postgres.search import SearchQuery, SearchRank
    from buraq.contrib.postgres.aggregates import ArrayAgg, StringAgg, JsonAgg
"""
