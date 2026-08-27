from collections.abc import AsyncIterator
from typing import Any, TypeVar

import sqlalchemy as sa
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update

from buraq.orm.prefetch import Prefetch

T = TypeVar("T")

# ── Fetch mode constants ──────────────────────────────────────────────────────

FETCH_ONE   = "FETCH_ONE"    # default — fetch only for current instance
FETCH_PEERS = "FETCH_PEERS"  # on-demand prefetch across all queryset peers
FETCH_RAISE = "FETCH_RAISE"  # raise FieldFetchBlocked on any deferred access


class FieldFetchBlocked(Exception):
    """Raised when FETCH_RAISE mode is active and a deferred field is accessed."""


class DoesNotExist(Exception):
    pass


class MultipleObjectsReturned(Exception):
    pass


def _apply_order_fields(model_class, query, fields):
    """Apply ordering field names to a query; a leading ``-`` means descending."""
    for field in fields:
        col = getattr(model_class, field.lstrip("-"), None)
        if col is None:
            continue
        query = query.order_by(col.desc() if field.startswith("-") else col)
    return query


def _default_ordering(model_class):
    """``Meta.ordering`` for a model, or an empty tuple."""
    return tuple(getattr(getattr(model_class, "_meta", None), "ordering", ()) or ())


class QuerySet:
    """
    Chainable async query builder.

    Usage:
        await Post.objects.all()
        await Post.objects.filter(author_id=1).order_by("-id").limit(10)
        await Post.objects.filter(Q(title__contains="hello") | Q(published=True))
        await Post.objects.values("title", "author_id")
        await Post.objects.aggregate(total=Count("id"))
    """

    def __init__(self, model_class: type, query=None):
        self._model = model_class
        if query is None:
            # A fresh queryset starts with Meta.ordering applied; an explicit
            # .order_by() later replaces it.
            query = _apply_order_fields(
                model_class, select(model_class), _default_ordering(model_class)
            )
        self._query = query
        self._values_fields: list | None = None
        self._flat: bool = False
        self._fetch_mode: str = FETCH_ONE
        self._peers: list | None = None  # populated after all() when FETCH_PEERS
        self._select_related_fields: list[str] = []
        self._prefetch_objs: list = []  # Prefetch instances, applied after the main query

    # ── Chaining methods (return new QuerySet) ──────────────────────────────

    def filter(self, *q_objs, **kwargs) -> "QuerySet":
        from buraq.orm.query import F, Q, _resolve_lookup
        q = self._query
        for q_obj in q_objs:
            if isinstance(q_obj, Q):
                q = q.where(q_obj.resolve(self._model))
            elif hasattr(q_obj, "resolve"):
                # Supports SearchQuery and any other resolvable filter objects
                q = q.where(q_obj.resolve(self._model))
        for key, value in kwargs.items():
            if isinstance(value, F):
                value = value.resolve(self._model)
            q = q.where(_resolve_lookup(self._model, key, value))
        qs = self._clone(q)
        return qs

    def exclude(self, *q_objs, **kwargs) -> "QuerySet":
        from buraq.orm.query import Q, _resolve_lookup
        q = self._query
        for q_obj in q_objs:
            if isinstance(q_obj, Q):
                q = q.where(sa.not_(q_obj.resolve(self._model)))
        for key, value in kwargs.items():
            if "__" in key:
                from buraq.orm.query import _resolve_lookup
                clause = _resolve_lookup(self._model, key, value)
                q = q.where(sa.not_(clause))
            else:
                col = getattr(self._model, key)
                q = q.where(col != value)
        return self._clone(q)

    def order_by(self, *fields: str) -> "QuerySet":
        """
        Order the results, replacing any ordering already applied — including
        the model's ``Meta.ordering`` default.

        Call with no arguments to clear ordering entirely.
        """
        q = self._query.order_by(None)
        return self._clone(_apply_order_fields(self._model, q, fields))

    def limit(self, n: int) -> "QuerySet":
        return self._clone(self._query.limit(n))

    def offset(self, n: int) -> "QuerySet":
        return self._clone(self._query.offset(n))

    def distinct(self) -> "QuerySet":
        return self._clone(self._query.distinct())

    def none(self) -> "QuerySet":
        return self._clone(self._query.where(sa.false()))

    def using(self, db) -> "QuerySet":
        raise NotImplementedError(
            "Multi-database routing via using() is not yet implemented in Buraq. "
            "All queries use the single DATABASE_URL connection."
        )

    def select_related(self, *fields) -> "QuerySet":
        """
        Eager-load forward foreign keys.

        A ``ForeignKey`` field holds only the raw related id until its name is
        passed here — after this, and only after the query has actually run,
        the same attribute holds the related instance instead. Two queries
        total (the source rows, then one batch fetch per related model), not
        a SQL join: ``ForeignKey`` fields are plain integer columns, not
        SQLAlchemy relationships, so there is no join to hook a loader
        strategy onto. Still O(1) additional queries regardless of row count,
        which is the property that actually matters — no per-row queries.

        Unlisted fields, and fields on a queryset this was never called on,
        are untouched: reading them still returns the raw id, exactly as
        before. There is no lazy auto-fetch on plain attribute access — that
        would mean a blocking query outside any query you asked for, which a
        fully async ORM does not do silently.
        """
        qs = self._clone()
        buraq_fks = getattr(self._model, "__buraq_fks__", {}) or {}
        qs._select_related_fields = list(self._select_related_fields) + [
            f for f in fields if f in buraq_fks and f not in self._select_related_fields
        ]
        return qs

    def prefetch_related(self, *fields) -> "QuerySet":
        """
        Batch-fetch reverse foreign key and many-to-many relations.

        Accepts plain field names or ``Prefetch`` instances (for a custom
        queryset or ``to_attr``). Applied after the main query runs, as a
        separate batched query per relation — see ``Prefetch.apply()``.
        Once applied, the relation's own accessor (``parent.children.all()``)
        returns the cached list instead of issuing a query.
        """
        qs = self._clone()
        objs = list(self._prefetch_objs)
        for field in fields:
            objs.append(field if isinstance(field, Prefetch) else Prefetch(field))
        qs._prefetch_objs = objs
        return qs

    async def _apply_select_related(self, instances: list) -> None:
        buraq_fks = getattr(self._model, "__buraq_fks__", {}) or {}
        for field_name in self._select_related_fields:
            fk = buraq_fks.get(field_name)
            target_model = getattr(fk, "_to", None) if fk else None
            if not isinstance(target_model, type):
                continue  # unresolved string reference — leave the raw id in place
            related_ids = {
                getattr(obj, field_name) for obj in instances
                if getattr(obj, field_name, None) is not None
            }
            if not related_ids:
                continue
            related = await QuerySet(target_model).filter(id__in=list(related_ids)).all()
            by_id = {obj.id: obj for obj in related}
            for obj in instances:
                fk_value = getattr(obj, field_name, None)
                if fk_value in by_id:
                    setattr(obj, field_name, by_id[fk_value])

    async def _apply_prefetch_related(self, instances: list) -> None:
        for prefetch in self._prefetch_objs:
            await prefetch.apply(instances)

    def values(self, *fields) -> "QuerySet":
        if fields:
            cols = [getattr(self._model, f) for f in fields]
            new_q = self._query.with_only_columns(*cols, maintain_column_froms=True)
            qs = self._clone(new_q)
            qs._values_fields = list(fields)
        else:
            qs = self._clone(self._query)
            qs._values_fields = None
        return qs

    def values_list(self, *fields, flat: bool = False) -> "QuerySet":
        qs = self.values(*fields)
        qs._flat = flat
        return qs

    def only(self, *fields) -> "QuerySet":
        from sqlalchemy.orm import load_only
        attrs = [getattr(self._model, f) for f in fields]
        q = self._query.options(load_only(*attrs))
        return self._clone(q)

    def defer(self, *fields) -> "QuerySet":
        from sqlalchemy.orm import defer as sa_defer
        q = self._query
        for field in fields:
            q = q.options(sa_defer(getattr(self._model, field)))
        return self._clone(q)

    def select_for_update(self, nowait: bool = False, skip_locked: bool = False) -> "QuerySet":
        """Lock selected rows with SELECT ... FOR UPDATE."""
        q = self._query.with_for_update(nowait=nowait, skip_locked=skip_locked)
        return self._clone(q)

    def union(self, *other_qs, all: bool = False) -> "QuerySet":
        """Combine querysets with UNION (or UNION ALL)."""
        result = self._query
        for qs in other_qs:
            result = result.union_all(qs._query) if all else result.union(qs._query)
        return self._clone(result)

    def intersection(self, *other_qs) -> "QuerySet":
        """Combine querysets with INTERSECT."""
        result = self._query
        for qs in other_qs:
            result = result.intersect(qs._query)
        return self._clone(result)

    def difference(self, *other_qs) -> "QuerySet":
        """Combine querysets with EXCEPT."""
        result = self._query
        for qs in other_qs:
            result = result.except_(qs._query)
        return self._clone(result)

    def fetch_mode(self, mode: str) -> "QuerySet":
        """
        Set the fetch mode for deferred field access on instances from this queryset.

        :param mode: One of ``FETCH_ONE``, ``FETCH_PEERS``, or ``FETCH_RAISE``.

        * ``FETCH_ONE`` (default) — missing fields are fetched for the current instance only.
        * ``FETCH_PEERS`` — on first deferred access, all peers from this queryset are
          bulk-loaded together (like an on-demand ``prefetch_related``).
        * ``FETCH_RAISE`` — accessing an unfetched field raises ``FieldFetchBlocked``.

        Usage::

            books = await Book.objects.fetch_mode(FETCH_PEERS).all()
            # Accessing any deferred field triggers a bulk load of that field
            # across all instances — prevents the N+1 queries problem.

            qs = Post.objects.fetch_mode(FETCH_RAISE)
            # Accessing a deferred field later raises FieldFetchBlocked.
        """
        if mode not in (FETCH_ONE, FETCH_PEERS, FETCH_RAISE):
            raise ValueError(
                f"fetch_mode must be one of FETCH_ONE, FETCH_PEERS, FETCH_RAISE; got {mode!r}"
            )
        qs = self._clone()
        qs._fetch_mode = mode
        return qs

    @property
    def totally_ordered(self) -> bool:
        """
        Return True if this queryset has a deterministic ordering.

        A queryset is totally ordered when it has at least one ``ORDER BY``
        clause AND at least one of those clauses is on the primary key (or
        a unique field), making the ordering unambiguous even across pages.

        Usage::

            qs = Post.objects.order_by("id")
            assert qs.totally_ordered is True

            qs = Post.objects.order_by("created_at")
            assert qs.totally_ordered is False  # ties possible
        """
        order_by = self._query._order_by_clauses
        if not order_by:
            return False
        pk_col = getattr(self._model, "id", None)
        if pk_col is None:
            return True  # can't inspect; assume ordered
        pk_key = getattr(pk_col, "key", None)
        for clause in order_by:
            col = getattr(clause, "element", clause)
            key = getattr(col, "key", None)
            if key and pk_key and key == pk_key:
                return True
        return False

    def extra(self, select=None, where=None, params=None, tables=None,
              order_by=None, select_params=None) -> "QuerySet":
        """
        Add raw SQL fragments to the query.

        Only `select` and `where` are implemented. `tables`, `order_by`,
        and `select_params` are accepted for API compatibility but ignored.
        """
        q = self._query
        if where:
            for clause in (where if isinstance(where, (list, tuple)) else [where]):
                q = q.where(sa.text(clause))
        if select:
            for label, expr in (select.items() if isinstance(select, dict) else select):
                q = q.add_columns(sa.literal_column(expr).label(label))
        return self._clone(q)

    def alias(self, **kwargs) -> "QuerySet":
        """
        Add named subquery aliases that can be reused in further filter/annotate calls.

        Example:
            qs = Post.objects.alias(
                comment_count=Count("comments"),
            ).filter(comment_count__gt=5)
        """
        q = self._query
        for label, expr in kwargs.items():
            col = expr.resolve(self._model) if hasattr(expr, "resolve") else expr
            q = q.add_columns(col.label(label))
        return self._clone(q)

    def annotate_expr(self, **kwargs) -> "QuerySet":
        """Add arbitrary SQLAlchemy expression columns via .label()."""
        q = self._query
        for label, expr in kwargs.items():
            if hasattr(expr, "resolve"):
                # Standard resolvable objects (Aggregate, ExpressionWrapper, etc.)
                col = expr.resolve(self._model)
            elif callable(expr):
                # Callable builders like SearchRank("field", "query") and SearchVector(...)
                col = expr(self._model)
            else:
                col = expr
            q = q.add_columns(col.label(label))
        return self._clone(q)

    # ── Async terminal methods ──────────────────────────────────────────────

    async def all(self) -> list:
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.execute(self._query)
            if self._values_fields is not None:
                rows = result.all()
                if self._flat and len(self._values_fields) == 1:
                    return [row[0] for row in rows]
                return [dict(zip(self._values_fields, row, strict=False)) for row in rows]
            instances = list(result.scalars().all())

        if self._fetch_mode == FETCH_PEERS and instances:
            # Store peer list on each instance for on-demand bulk loading
            for obj in instances:
                obj._qs_peers = instances
                obj._qs_fetch_mode = FETCH_PEERS
        elif self._fetch_mode == FETCH_RAISE and instances:
            for obj in instances:
                obj._qs_fetch_mode = FETCH_RAISE

        if instances and self._select_related_fields:
            await self._apply_select_related(instances)
        if instances and self._prefetch_objs:
            await self._apply_prefetch_related(instances)

        return instances

    async def first(self) -> Any | None:
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.execute(self._query.limit(1))
            if self._values_fields is not None:
                row = result.first()
                if row is None:
                    return None
                if self._flat and len(self._values_fields) == 1:
                    return row[0]
                return dict(zip(self._values_fields, row, strict=False))
            instance = result.scalar_one_or_none()

        if instance is not None:
            if self._select_related_fields:
                await self._apply_select_related([instance])
            if self._prefetch_objs:
                await self._apply_prefetch_related([instance])
        return instance

    async def last(self) -> Any | None:
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        pk_col = getattr(self._model, "id", None)
        if pk_col is not None:
            q = self._query.order_by(None).order_by(sa.desc(pk_col)).limit(1)
        else:
            q = self._query
        async with SessionLocal() as db:
            result = await db.execute(q)
            return result.scalar_one_or_none()

    async def count(self) -> int:
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            q = select(func.count()).select_from(self._query.subquery())
            result = await db.execute(q)
            return result.scalar() or 0

    async def exists(self) -> bool:
        from buraq.core.db import SessionLocal
        q = sa.select(sa.literal(1)).select_from(self._query.subquery()).limit(1)
        async with SessionLocal() as db:
            result = await db.execute(q)
            return result.first() is not None

    async def get(self, *q_objs, **kwargs) -> Any:
        """
        The one matching row, filtered further by ``*q_objs``/``**kwargs``.

        Available on ``QuerySet`` itself (not only ``Manager.get()``) so it
        can end a chain: ``await Post.objects.select_related("author").get(id=1)``.
        """
        # Fetch at most 2 rows — enough to detect duplicates without loading the whole table.
        items = await self.filter(*q_objs, **kwargs).limit(2).all()
        if not items:
            raise self._model.DoesNotExist(f"{self._model.__name__} matching query does not exist.")
        if len(items) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self._model.__name__}."
            )
        return items[0]

    async def get_or_none(self, *q_objs, **kwargs) -> Any | None:
        """Like ``get()``, but ``None`` instead of raising when no row matches."""
        try:
            return await self.get(*q_objs, **kwargs)
        except DoesNotExist:
            return None

    async def delete(self) -> int:
        """Bulk delete all rows matching current filters."""
        from buraq.core.db import SessionLocal, _current_session
        where_clauses = self._query.whereclause
        q = sa_delete(self._model)
        if where_clauses is not None:
            q = q.where(where_clauses)
        active = _current_session.get()
        if active is not None:
            result = await active.execute(q)
            await active.flush()
            return result.rowcount
        async with SessionLocal() as db:
            result = await db.execute(q)
            await db.commit()
            return result.rowcount

    async def update(self, **kwargs) -> int:
        """Bulk update all rows matching current filters."""
        from buraq.core.db import SessionLocal, _current_session
        from buraq.orm.query import F, _FExpr
        resolved = {}
        for key, value in kwargs.items():
            if isinstance(value, (F, _FExpr)):
                resolved[key] = value.resolve(self._model)
            else:
                resolved[key] = value
        where_clauses = self._query.whereclause
        q = sa_update(self._model).values(**resolved)
        if where_clauses is not None:
            q = q.where(where_clauses)
        active = _current_session.get()
        if active is not None:
            result = await active.execute(q)
            await active.flush()
            return result.rowcount
        async with SessionLocal() as db:
            result = await db.execute(q)
            await db.commit()
            return result.rowcount

    async def aggregate(self, **kwargs) -> dict:
        """
        Run aggregate functions and return a dict.

        Example:
            result = await Post.objects.aggregate(total=Count("id"), avg=Avg("views"))
            # → {"total": 42, "avg": 7.3}
        """
        from buraq.core.db import SessionLocal
        from buraq.orm.aggregates import Aggregate
        cols = []
        labels = []
        for label, agg in kwargs.items():
            if isinstance(agg, Aggregate):
                cols.append(agg.resolve(self._model).label(label))
            else:
                cols.append(sa.literal(agg).label(label))
            labels.append(label)

        base = self._query.subquery()
        q = select(*cols).select_from(base)
        async with SessionLocal() as db:
            result = await db.execute(q)
            row = result.first()
            if row is None:
                return {label: None for label in labels}
            return dict(zip(labels, row, strict=False))

    async def annotate(self, **kwargs) -> list:
        """
        Add computed columns to each result row.

        Example:
            qs = await Post.objects.values("author_id").annotate(count=Count("id"))
        """
        from buraq.core.db import SessionLocal
        from buraq.orm.aggregates import Aggregate

        # Build select with base columns + annotations
        if self._values_fields:
            base_cols = [getattr(self._model, f) for f in self._values_fields]
            group_by = base_cols[:]
        else:
            base_cols = [self._model]
            group_by = []

        agg_cols = []
        agg_labels = []
        for label, agg in kwargs.items():
            if isinstance(agg, Aggregate):
                agg_cols.append(agg.resolve(self._model).label(label))
            else:
                agg_cols.append(sa.literal(agg).label(label))
            agg_labels.append(label)

        all_cols = base_cols + agg_cols
        q = select(*all_cols)
        if group_by:
            q = q.group_by(*group_by)
        if self._query.whereclause is not None:
            q = q.where(self._query.whereclause)

        async with SessionLocal() as db:
            result = await db.execute(q)
            rows = result.all()
            all_labels = (self._values_fields or []) + agg_labels
            return [dict(zip(all_labels, row, strict=False)) for row in rows]

    async def iterator(self) -> AsyncIterator:
        """Async generator yielding one row at a time."""
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.stream_scalars(self._query)
            async for row in result:
                yield row

    def _latest_by_fields(self) -> tuple[str, ...]:
        """Default ordering for latest()/earliest(): Meta.get_latest_by, else pk."""
        configured = getattr(getattr(self._model, "_meta", None), "get_latest_by", None)
        if not configured:
            return ("id",)
        return (configured,) if isinstance(configured, str) else tuple(configured)

    async def earliest(self, *fields: str) -> Any | None:
        """
        Earliest object by the given field(s).

        With no arguments this uses ``Meta.get_latest_by``, falling back to the
        primary key. A leading ``-`` reverses that field.
        """
        q = self._query.order_by(None)
        for f in fields or self._latest_by_fields():
            col = getattr(self._model, f.lstrip("-"))
            q = q.order_by(col.desc() if f.startswith("-") else col)
        return await self._clone(q).first()

    async def latest(self, *fields: str) -> Any | None:
        """
        Latest object by the given field(s) — the reverse of :meth:`earliest`.

        With no arguments this uses ``Meta.get_latest_by``, falling back to the
        primary key.
        """
        q = self._query.order_by(None)
        for f in fields or self._latest_by_fields():
            col = getattr(self._model, f.lstrip("-"))
            q = q.order_by(col if f.startswith("-") else col.desc())
        return await self._clone(q).first()

    async def dates(self, field: str, kind: str) -> list:
        """
        Return a list of distinct date values for the given field, truncated by kind.

        kind: "year" | "month" | "day"
        """
        from sqlalchemy.engine import make_url as _make_url

        from buraq.conf import settings
        from buraq.core.db import SessionLocal
        col = getattr(self._model, field)
        try:
            dialect = _make_url(settings.DATABASE_URL).get_dialect().name
        except Exception:
            dialect = "postgresql"
        if dialect == "sqlite":
            _fmt = {"year": "%Y-01-01", "month": "%Y-%m-01", "day": "%Y-%m-%d"}
            trunc = sa.cast(func.strftime(_fmt.get(kind, "%Y-%m-%d"), col), sa.Date)
        elif dialect in ("mysql", "mariadb"):
            _fmt = {"year": "%Y-01-01", "month": "%Y-%m-01", "day": "%Y-%m-%d"}
            trunc = sa.cast(func.date_format(col, _fmt.get(kind, "%Y-%m-%d")), sa.Date)
        else:
            trunc = sa.cast(func.date_trunc(kind, col), sa.Date)
        q = sa.select(trunc.label("date")).distinct().order_by(trunc)
        async with SessionLocal() as db:
            result = await db.execute(q)
            return [row[0] for row in result.all()]

    async def datetimes(self, field: str, kind: str) -> list:
        """
        Return a list of distinct datetime values for the given field, truncated by kind.

        kind: "year" | "month" | "day" | "hour" | "minute" | "second"
        """
        from sqlalchemy.engine import make_url as _make_url

        from buraq.conf import settings
        from buraq.core.db import SessionLocal
        col = getattr(self._model, field)
        try:
            dialect = _make_url(settings.DATABASE_URL).get_dialect().name
        except Exception:
            dialect = "postgresql"
        if dialect == "sqlite":
            _fmt = {
                "year": "%Y-01-01 00:00:00", "month": "%Y-%m-01 00:00:00",
                "day": "%Y-%m-%d 00:00:00", "hour": "%Y-%m-%d %H:00:00",
                "minute": "%Y-%m-%d %H:%M:00", "second": "%Y-%m-%d %H:%M:%S",
            }
            trunc = sa.cast(func.strftime(_fmt.get(kind, "%Y-%m-%d %H:%M:%S"), col), sa.DateTime)
        elif dialect in ("mysql", "mariadb"):
            _fmt = {
                "year": "%Y-01-01 00:00:00", "month": "%Y-%m-01 00:00:00",
                "day": "%Y-%m-%d 00:00:00", "hour": "%Y-%m-%d %H:00:00",
                "minute": "%Y-%m-%d %H:%i:00", "second": "%Y-%m-%d %H:%i:%S",
            }
            trunc = sa.cast(func.date_format(col, _fmt.get(kind, "%Y-%m-%d %H:%i:%S")), sa.DateTime)
        else:
            trunc = func.date_trunc(kind, col)
        q = sa.select(trunc.label("dt")).distinct().order_by(trunc)
        async with SessionLocal() as db:
            result = await db.execute(q)
            return [row[0] for row in result.all()]

    async def raw(self, sql: str, params: dict | list | None = None) -> list:
        """Execute raw SQL and return rows as dicts."""
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.execute(sa.text(sql), params or {})
            keys = list(result.keys())
            return [dict(zip(keys, row, strict=False)) for row in result.all()]

    async def explain(self, *, analyze: bool = False, verbose: bool = False) -> str:
        """
        Return the database query plan as a string.

        Args:
            analyze: Run EXPLAIN ANALYZE (executes the query).
            verbose: Include extra plan detail (EXPLAIN VERBOSE on PostgreSQL).

        Example:
            plan = await Post.objects.filter(is_published=True).explain()
        """
        from sqlalchemy.engine import make_url as _make_url

        from buraq.conf import settings
        from buraq.core.db import SessionLocal
        try:
            dialect = _make_url(settings.DATABASE_URL).get_dialect().name
        except Exception:
            dialect = "postgresql"

        if dialect == "sqlite":
            prefix = "EXPLAIN QUERY PLAN"
        elif dialect in ("mysql", "mariadb"):
            prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
        else:
            parts = ["EXPLAIN"]
            if analyze:
                parts.append("ANALYZE")
            if verbose:
                parts.append("VERBOSE")
            prefix = " ".join(parts)

        compiled = self._query.compile(compile_kwargs={"literal_binds": True})
        raw_sql = f"{prefix} {compiled}"
        async with SessionLocal() as db:
            result = await db.execute(sa.text(raw_sql))
            rows = result.fetchall()
        return "\n".join(" | ".join(str(c) for c in row) for row in rows)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _clone(self, query=None) -> "QuerySet":
        qs = QuerySet(self._model, query if query is not None else self._query)
        qs._values_fields = self._values_fields
        qs._flat = self._flat
        qs._fetch_mode = self._fetch_mode
        qs._select_related_fields = list(self._select_related_fields)
        qs._prefetch_objs = list(self._prefetch_objs)
        return qs

    # Allow `await Post.objects.filter(...)` directly
    def __await__(self):
        return self.all().__await__()

    def __aiter__(self):
        return self.iterator()


class RelatedManager:
    """
    Manager returned by reverse FK accessors, e.g. ``post.comment_set``.

    Automatically filters by the FK column pointing back to the parent instance.
    """

    def __init__(self, model_class: type, fk_field: str, instance, attr_name: str = ""):
        self._model = model_class
        self._fk_field = fk_field
        self._instance = instance
        self._attr_name = attr_name

    def _base_qs(self) -> "QuerySet":
        return QuerySet(self._model).filter(**{self._fk_field: self._instance.id})

    def all(self):
        """
        The prefetched list if ``prefetch_related(attr_name)`` populated one
        on this instance — plain, already in memory, no query. Otherwise a
        lazy ``QuerySet``, exactly as before: ``await`` it or iterate with
        ``async for``.
        """
        if self._attr_name:
            cached = getattr(self._instance, f"_prefetched_{self._attr_name}", None)
            if cached is not None:
                return cached
        return self._base_qs()

    def filter(self, *q_objs, **kwargs) -> "QuerySet":
        return self._base_qs().filter(*q_objs, **kwargs)

    def exclude(self, *q_objs, **kwargs) -> "QuerySet":
        return self._base_qs().exclude(*q_objs, **kwargs)

    def order_by(self, *fields: str) -> "QuerySet":
        return self._base_qs().order_by(*fields)

    async def count(self) -> int:
        return await self._base_qs().count()

    async def create(self, **kwargs) -> Any:
        kwargs[self._fk_field] = self._instance.id
        manager = Manager(self._model)
        return await manager.create(**kwargs)

    async def get(self, **kwargs) -> Any:
        items = await self._base_qs().filter(**kwargs).limit(2).all()
        if not items:
            raise DoesNotExist(
                f"{self._model.__name__} matching query does not exist."
            )
        if len(items) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self._model.__name__}."
            )
        return items[0]

    async def add(self, *objs) -> None:
        if not objs:
            return
        ids = [obj.id for obj in objs]
        await Manager(self._model).filter(id__in=ids).update(
            **{self._fk_field: self._instance.id}
        )
        for obj in objs:
            setattr(obj, self._fk_field, self._instance.id)

    async def remove(self, *objs) -> None:
        if not objs:
            return
        ids = [obj.id for obj in objs]
        await Manager(self._model).filter(id__in=ids).update(
            **{self._fk_field: None}
        )
        for obj in objs:
            setattr(obj, self._fk_field, None)

    async def clear(self) -> None:
        await self._base_qs().update(**{self._fk_field: None})

    async def set(self, objs) -> None:
        await self.clear()
        await self.add(*objs)

    def __await__(self):
        return self._base_qs().all().__await__()


class _ReverseFKDescriptor:
    """Descriptor set on a parent model to provide ``parent.child_set`` accessor."""

    def __init__(self, child_model_getter, fk_field: str, attr_name: str):
        self._child_model_getter = child_model_getter
        self._fk_field = fk_field
        self._attr_name = attr_name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        getter = self._child_model_getter
        # A class is itself callable (calling it builds an instance), so the
        # "is this a lazy resolver" check must exclude classes explicitly —
        # otherwise resolving an already-resolved model class here builds a
        # blank instance of it instead of using the class.
        child_model = getter() if callable(getter) and not isinstance(getter, type) else getter
        return RelatedManager(child_model, self._fk_field, instance, self._attr_name)


class Manager:
    """
    Async ORM manager attached to every Model as `.objects`.
    """

    def __init__(self, model_class: type | None = None):
        # Managers declared on a model (``objects = MyManager()``) are bound to
        # the class later by the model metaclass, so the model is optional here.
        self._model = model_class

    # ── QuerySet factory shortcuts ──────────────────────────────────────────

    def all(self) -> QuerySet:
        return QuerySet(self._model)

    def none(self) -> QuerySet:
        return QuerySet(self._model).none()

    def filter(self, *q_objs, **kwargs) -> QuerySet:
        return QuerySet(self._model).filter(*q_objs, **kwargs)

    def exclude(self, *q_objs, **kwargs) -> QuerySet:
        return QuerySet(self._model).exclude(*q_objs, **kwargs)

    def order_by(self, *fields: str) -> QuerySet:
        return QuerySet(self._model).order_by(*fields)

    def values(self, *fields) -> QuerySet:
        return QuerySet(self._model).values(*fields)

    def values_list(self, *fields, flat: bool = False) -> QuerySet:
        return QuerySet(self._model).values_list(*fields, flat=flat)

    def distinct(self) -> QuerySet:
        return QuerySet(self._model).distinct()

    def select_related(self, *fields) -> QuerySet:
        return QuerySet(self._model).select_related(*fields)

    def prefetch_related(self, *fields) -> QuerySet:
        return QuerySet(self._model).prefetch_related(*fields)

    # ── Single-object methods ───────────────────────────────────────────────

    async def get(self, *q_objs, **kwargs) -> Any:
        return await QuerySet(self._model).get(*q_objs, **kwargs)

    async def get_or_none(self, *q_objs, **kwargs) -> Any | None:
        return await QuerySet(self._model).get_or_none(*q_objs, **kwargs)

    # ── Write methods ───────────────────────────────────────────────────────

    async def create(self, **kwargs) -> Any:
        from buraq.core.db import SessionLocal, _current_session
        active = _current_session.get()
        if active is not None:
            obj = self._model(**kwargs)
            active.add(obj)
            await active.flush()
            await active.refresh(obj)
            return obj
        async with SessionLocal() as db:
            obj = self._model(**kwargs)
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
            return obj

    async def get_or_create(self, defaults: dict | None = None, **kwargs) -> tuple:
        # SELECT-first avoids triggering IntegrityError (and a full transaction rollback)
        # on every call for an already-existing row.
        obj = await self.get_or_none(**kwargs)
        if obj is not None:
            return obj, False
        from sqlalchemy.exc import IntegrityError
        try:
            obj = await self.create(**{**kwargs, **(defaults or {})})
            return obj, True
        except IntegrityError:
            # Concurrent insert won the race — fetch the existing row.
            obj = await self.get(**kwargs)
            return obj, False

    async def update_or_create(self, defaults: dict | None = None, **kwargs) -> tuple:
        # SELECT-first: fetch before attempting an insert.
        obj = await self.get_or_none(**kwargs)
        if obj is not None:
            for key, value in (defaults or {}).items():
                setattr(obj, key, value)
            await obj.save()
            return obj, False
        from sqlalchemy.exc import IntegrityError
        try:
            obj = await self.create(**{**kwargs, **(defaults or {})})
            return obj, True
        except IntegrityError:
            obj = await self.get(**kwargs)
            for key, value in (defaults or {}).items():
                setattr(obj, key, value)
            await obj.save()
            return obj, False

    async def update(self, pk: int, **kwargs) -> Any:
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.execute(
                select(self._model).where(self._model.id == pk)
            )
            obj = result.scalar_one_or_none()
            if not obj:
                raise DoesNotExist(
                    f"{self._model.__name__} with id={pk} does not exist."
                )
            for key, value in kwargs.items():
                setattr(obj, key, value)
            await db.commit()
            await db.refresh(obj)
            return obj

    async def delete(self, pk: int) -> None:
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.execute(
                select(self._model).where(self._model.id == pk)
            )
            obj = result.scalar_one_or_none()
            if not obj:
                raise DoesNotExist(
                    f"{self._model.__name__} with id={pk} does not exist."
                )
            await db.delete(obj)
            await db.commit()

    async def bulk_create(self, records: list[dict], ignore_conflicts: bool = False) -> list:
        from sqlalchemy.engine import make_url as _make_url

        from buraq.core.db import SessionLocal, _current_session
        col_names = {c.name for c in self._model.__table__.columns}
        clean_records = [{k: v for k, v in r.items() if k in col_names} for r in records]
        active = _current_session.get()
        if ignore_conflicts:
            from buraq.conf import settings
            try:
                dialect = _make_url(settings.DATABASE_URL).get_dialect().name
            except Exception:
                dialect = "postgresql"
            if dialect == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as _insert
            elif dialect in ("mysql", "mariadb"):
                from sqlalchemy.dialects.mysql import insert as _insert  # type: ignore[no-redef]
            else:
                from sqlalchemy.dialects.postgresql import (
                    insert as _insert,  # type: ignore[no-redef]
                )
            stmt = _insert(self._model.__table__).values(clean_records).on_conflict_do_nothing()
            if active is not None:
                await active.execute(stmt)
                await active.flush()
            else:
                async with SessionLocal() as db:
                    await db.execute(stmt)
                    await db.commit()
            return []
        instances = [self._model(**rec) for rec in clean_records]
        if active is not None:
            active.add_all(instances)
            await active.flush()
        else:
            async with SessionLocal() as db:
                db.add_all(instances)
                await db.commit()
        return instances

    async def bulk_update(self, objs: list, fields: list) -> int:
        if not objs:
            return 0
        from buraq.core.db import SessionLocal
        # Build a list of dicts {id, field1, field2, ...} for bulk parameter binding.
        # SQLAlchemy executes this as a single round-trip with multi-row binding.
        params = [{"_pk": obj.id, **{f: getattr(obj, f) for f in fields}} for obj in objs]
        stmt = (
            sa_update(self._model)
            .where(self._model.id == sa.bindparam("_pk"))
            .values({f: sa.bindparam(f) for f in fields})
        )
        async with SessionLocal() as db:
            await db.execute(stmt, params)
            await db.commit()
        return len(objs)

    async def count(self) -> int:
        return await QuerySet(self._model).count()

    async def exists(self) -> bool:
        """True if the table has any rows. Mirrors ``QuerySet.exists()``."""
        return await QuerySet(self._model).exists()

    async def first(self) -> Any | None:
        """First row by default ordering, or ``None``. Mirrors ``QuerySet.first()``."""
        return await QuerySet(self._model).first()

    async def last(self) -> Any | None:
        """Last row by default ordering, or ``None``. Mirrors ``QuerySet.last()``."""
        return await QuerySet(self._model).last()

    async def aggregate(self, **kwargs) -> dict:
        return await QuerySet(self._model).aggregate(**kwargs)

    async def in_bulk(self, id_list: list, field_name: str = "id") -> dict:
        """
        Return a dict mapping ``{field_value: instance}`` for the given IDs.

        Supports chaining after ``values()`` / ``values_list()``::

            mapping = await Post.objects.values("id", "title").in_bulk([1, 2, 3])
            # → {1: {"id": 1, "title": "..."}, ...}
        """
        qs = QuerySet(self._model).filter(**{f"{field_name}__in": id_list})
        items = await qs.all()
        if items and isinstance(items[0], dict):
            return {item[field_name]: item for item in items}
        return {getattr(item, field_name): item for item in items}

    def select_for_update(self, nowait: bool = False, skip_locked: bool = False) -> QuerySet:
        return QuerySet(self._model).select_for_update(nowait=nowait, skip_locked=skip_locked)

    async def earliest(self, *fields: str) -> Any | None:
        return await QuerySet(self._model).earliest(*fields)

    async def latest(self, *fields: str) -> Any | None:
        return await QuerySet(self._model).latest(*fields)

    async def dates(self, field: str, kind: str) -> list:
        return await QuerySet(self._model).dates(field, kind)

    async def datetimes(self, field: str, kind: str) -> list:
        return await QuerySet(self._model).datetimes(field, kind)

    async def raw(self, sql: str, params: dict | list | None = None) -> list:
        return await QuerySet(self._model).raw(sql, params)
