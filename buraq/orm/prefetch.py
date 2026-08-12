"""
Prefetch — customize queryset used when prefetching a related object set.

Usage:
    from buraq.orm.prefetch import Prefetch

    # Load only approved comments, ordered by date
    posts = await Post.objects.prefetch_related(
        Prefetch("comments", queryset=Comment.objects.filter(approved=True).order_by("-created_at"))
    ).all()
    # Access pre-fetched comments as post._prefetched_comments
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
        Fetch related objects and attach them to each instance.

        Called automatically by ``QuerySet.all()`` when Prefetch objects are present.
        """
        if not instances or self.queryset is None:
            return

        attr = self.to_attr or f"_prefetched_{self.field}"
        source_ids = [inst.id for inst in instances]

        # Determine the FK column on the related model that points back to the source.
        # Convention: <source_table_singular>_id  e.g.  post_id for Post → posts
        source_model = type(instances[0])
        fk_col = f"{source_model.__name__.lower()}_id"

        qs = self.queryset
        if hasattr(qs._model, fk_col):
            qs = qs.filter(**{f"{fk_col}__in": source_ids})

        related_objects = await qs.all()

        # Group by FK value
        grouped: dict = {}
        for obj in related_objects:
            key = getattr(obj, fk_col, None)
            grouped.setdefault(key, []).append(obj)

        for inst in instances:
            setattr(inst, attr, grouped.get(inst.id, []))
