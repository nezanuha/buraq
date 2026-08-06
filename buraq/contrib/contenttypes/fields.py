"""Generic foreign key descriptor for cross-model relations."""
from __future__ import annotations

import importlib


class GenericForeignKey:
    """
    Descriptor that resolves a (content_type_id, object_id) pair to any model instance.

    Usage:
        class Comment(Model):
            content_type_id = Column(Integer)
            object_id = Column(Integer)
            content_object = GenericForeignKey("content_type_id", "object_id")

        comment = await Comment.objects.get(id=1)
        post = await comment.content_object   # awaitable — returns the linked object
    """

    def __init__(self, ct_field: str = "content_type_id", fk_field: str = "object_id"):
        self.ct_field = ct_field
        self.fk_field = fk_field
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return self._resolve(instance)

    async def _resolve(self, instance):
        from buraq.contrib.contenttypes.models import ContentType
        ct_id = getattr(instance, self.ct_field)
        obj_id = getattr(instance, self.fk_field)
        if ct_id is None or obj_id is None:
            return None
        ct = await ContentType.objects.get_or_none(id=ct_id)
        if ct is None:
            return None
        try:
            module = importlib.import_module(ct.app_label)
            model_cls = next(
                v for v in vars(module).values()
                if isinstance(v, type) and getattr(v, "__name__", "").lower() == ct.model
            )
            return await model_cls.objects.get_or_none(id=obj_id)
        except (StopIteration, ImportError):
            return None
