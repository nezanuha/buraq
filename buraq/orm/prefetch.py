"""
Prefetch — customize queryset used when prefetching a related object set.

Usage:
    from buraq.orm.prefetch import Prefetch

    # Load only approved comments, ordered by date
    posts = await Post.objects.prefetch_related(
        Prefetch("comments", queryset=Comment.objects.filter(approved=True).order_by("-created_at"))
    ).all()
    # Access pre-fetched comments as post._prefetched_comments, or through the
    # normal accessor — post.comments.all() returns the cached list instead of
    # issuing a query once it has been prefetched.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buraq.orm.manager import QuerySet


class Prefetch:
    """
    Describes a custom prefetch operation for use with ``prefetch_related()``.

    Args:
        field:     The attribute name on the source model (e.g. ``"comments"``).
        queryset:  A :class:`~buraq.orm.manager.QuerySet` that filters / orders the
                   related objects. If omitted, all related objects are fetched.
        to_attr:   When given, stores the result on this attribute instead of
                   the default accessor.  Use to hold multiple filtered sets for
                   the same relation.
    """

    def __init__(
        self,
        field: str,
        queryset: QuerySet | None = None,
        to_attr: str | None = None,
    ):
        self.field = field
        self.queryset = queryset
        self.to_attr = to_attr

    async def apply(self, instances: list) -> None:
        """
        Fetch related objects (reverse foreign key or many-to-many) and
        attach them to each instance, so the accessor's ``.all()`` returns
        the cached list instead of issuing its own query.

        Called automatically by ``QuerySet.all()`` / ``.first()`` for every
        relation named in ``prefetch_related()``.
        """
        from buraq.orm.fields import _M2MDescriptor
        from buraq.orm.manager import QuerySet, _ReverseFKDescriptor

        if not instances:
            return

        source_model = type(instances[0])
        descriptor = getattr(source_model, self.field, None)
        attr = self.to_attr or f"_prefetched_{self.field}"
        source_ids = [inst.id for inst in instances]

        if isinstance(descriptor, _ReverseFKDescriptor):
            child_getter = descriptor._child_model_getter
            # A class is itself callable — exclude it explicitly, or resolving
            # an already-resolved class here builds a blank instance instead.
            child_model = (
                child_getter() if callable(child_getter) and not isinstance(child_getter, type)
                else child_getter
            )
            fk_field = descriptor._fk_field

            qs = self.queryset if self.queryset is not None else QuerySet(child_model)
            qs = qs.filter(**{f"{fk_field}__in": source_ids})
            related_objects = await qs.all()

            grouped: dict = {}
            for obj in related_objects:
                key = getattr(obj, fk_field, None)
                grouped.setdefault(key, []).append(obj)

            for inst in instances:
                setattr(inst, attr, grouped.get(inst.id, []))

        elif isinstance(descriptor, _M2MDescriptor):
            import sqlalchemy as sa

            from buraq.core.db import SessionLocal

            field = descriptor.field
            assoc = field._assoc_table
            to = field._to
            if isinstance(to, str) or assoc is None:
                for inst in instances:
                    setattr(inst, attr, [])
                return

            async with SessionLocal() as db:
                q = sa.select(assoc.c.source_id, to).join(
                    to, to.id == assoc.c.target_id
                ).where(assoc.c.source_id.in_(source_ids))
                result = await db.execute(q)
                rows = result.all()

            grouped = {}
            for source_id, obj in rows:
                grouped.setdefault(source_id, []).append(obj)

            for inst in instances:
                setattr(inst, attr, grouped.get(inst.id, []))

        # Anything else (an unrecognised or missing attribute) is left alone —
        # accessing it afterwards behaves exactly as it would have before
        # prefetch_related() was called.
