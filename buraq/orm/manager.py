from collections.abc import AsyncIterator
from typing import Any, TypeVar

import sqlalchemy as sa
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy import update as sa_update

T = TypeVar("T")


class DoesNotExist(Exception):
    pass


class MultipleObjectsReturned(Exception):
    pass


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
        self._query = query if query is not None else select(model_class)
        self._values_fields: list | None = None
        self._flat: bool = False

    # ── Chaining methods (return new QuerySet) ──────────────────────────────

    def filter(self, *q_objs, **kwargs) -> "QuerySet":
        from buraq.orm.query import F, Q, _resolve_lookup
        q = self._query
        # Apply Q objects
        for q_obj in q_objs:
            if isinstance(q_obj, Q):
                q = q.where(q_obj.resolve(self._model))
        # Apply kwargs
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
        q = self._query
        for field in fields:
            if field.startswith("-"):
                q = q.order_by(getattr(self._model, field[1:]).desc())
            else:
                q = q.order_by(getattr(self._model, field))
        return self._clone(q)

    def limit(self, n: int) -> "QuerySet":
        return self._clone(self._query.limit(n))

    def offset(self, n: int) -> "QuerySet":
        return self._clone(self._query.offset(n))

    def distinct(self) -> "QuerySet":
        return self._clone(self._query.distinct())

    def none(self) -> "QuerySet":
        return self._clone(self._query.where(sa.false()))

    def using(self, db) -> "QuerySet":
        return self

    def select_related(self, *fields) -> "QuerySet":
        from sqlalchemy.orm import joinedload
        q = self._query
        for field in fields:
            rel = getattr(self._model, field, None)
            if rel is not None:
                q = q.options(joinedload(rel))
        return self._clone(q)

    def prefetch_related(self, *fields) -> "QuerySet":
        from sqlalchemy.orm import selectinload
        q = self._query
        for field in fields:
            rel = getattr(self._model, field, None)
            if rel is not None:
                q = q.options(selectinload(rel))
        return self._clone(q)

    def values(self, *fields) -> "QuerySet":
        qs = self._clone(self._query)
        qs._values_fields = list(fields) if fields else None
        return qs

    def values_list(self, *fields, flat: bool = False) -> "QuerySet":
        qs = self.values(*fields)
        qs._flat = flat
        return qs

    def only(self, *fields) -> "QuerySet":
        cols = [getattr(self._model, f) for f in fields]
        return self._clone(select(*cols))

    def defer(self, *fields) -> "QuerySet":
        return self

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
            return list(result.scalars().all())

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
            return result.scalar_one_or_none()

    async def last(self) -> Any | None:
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        # Reverse primary key ordering and take 1 row — avoids loading the whole table.
        pk_col = getattr(self._model, "id", None)
        q = self._query.order_by(sa.desc(pk_col)).limit(1) if pk_col is not None else self._query
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
        return bool(await self.first())

    async def delete(self) -> int:
        """Bulk delete all rows matching current filters."""
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            # Extract WHERE clause from select query
            where_clauses = self._query.whereclause
            q = sa_delete(self._model)
            if where_clauses is not None:
                q = q.where(where_clauses)
            result = await db.execute(q)
            await db.commit()
            return result.rowcount

    async def update(self, **kwargs) -> int:
        """Bulk update all rows matching current filters."""
        from buraq.core.db import SessionLocal
        from buraq.orm.query import F, _FExpr
        async with SessionLocal() as db:
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

        all_cols = (
            [getattr(self._model, f) for f in (self._values_fields or [])] + agg_cols
        )
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

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _clone(self, query=None) -> "QuerySet":
        qs = QuerySet(self._model, query if query is not None else self._query)
        qs._values_fields = self._values_fields
        qs._flat = self._flat
        return qs

    # Allow `await Post.objects.filter(...)` directly
    def __await__(self):
        return self.all().__await__()

    def __aiter__(self):
        return self.iterator()


class Manager:
    """
    Async ORM manager attached to every Model as `.objects`.
    """

    def __init__(self, model_class: type):
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
        # Fetch at most 2 rows — enough to detect duplicates without loading the whole table.
        items = await self.filter(*q_objs, **kwargs).limit(2).all()
        if not items:
            raise DoesNotExist(f"{self._model.__name__} matching query does not exist.")
        if len(items) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self._model.__name__}."
            )
        return items[0]

    async def get_or_none(self, *q_objs, **kwargs) -> Any | None:
        try:
            return await self.get(*q_objs, **kwargs)
        except DoesNotExist:
            return None

    # ── Write methods ───────────────────────────────────────────────────────

    async def create(self, **kwargs) -> Any:
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            obj = self._model(**kwargs)
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
            return obj

    async def get_or_create(self, defaults: dict | None = None, **kwargs) -> tuple:
        obj = await self.get_or_none(**kwargs)
        if obj:
            return obj, False
        obj = await self.create(**{**kwargs, **(defaults or {})})
        return obj, True

    async def update_or_create(self, defaults: dict | None = None, **kwargs) -> tuple:
        obj = await self.get_or_none(**kwargs)
        if obj:
            for key, value in (defaults or {}).items():
                setattr(obj, key, value)
            await obj.save()
            return obj, False
        obj = await self.create(**{**kwargs, **(defaults or {})})
        return obj, True

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
        from buraq.core.db import SessionLocal
        # Use only column names as keys — never pass SA instance dicts (_sa_instance_state).
        col_names = {c.name for c in self._model.__table__.columns}
        clean_records = [{k: v for k, v in r.items() if k in col_names} for r in records]
        async with SessionLocal() as db:
            if ignore_conflicts:
                from buraq.conf import settings
                url = settings.DATABASE_URL
                if "sqlite" in url:
                    from sqlalchemy.dialects.sqlite import insert as _insert
                else:
                    from sqlalchemy.dialects.postgresql import insert as _insert
                stmt = _insert(self._model.__table__).values(clean_records).on_conflict_do_nothing()
                await db.execute(stmt)
                await db.commit()
                return []
            instances = [self._model(**rec) for rec in clean_records]
            db.add_all(instances)
            await db.commit()
            return instances

    async def bulk_update(self, objs: list, fields: list) -> int:
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            for obj in objs:
                data = {f: getattr(obj, f) for f in fields}
                await db.execute(
                    sa_update(self._model).where(self._model.id == obj.id).values(**data)
                )
            await db.commit()
            return len(objs)

    async def count(self) -> int:
        return await QuerySet(self._model).count()

    async def aggregate(self, **kwargs) -> dict:
        return await QuerySet(self._model).aggregate(**kwargs)

    async def in_bulk(self, id_list: list, field_name: str = "id") -> dict:
        items = await self.filter(**{f"{field_name}__in": id_list}).all()
        return {getattr(item, field_name): item for item in items}
