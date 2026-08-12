"""Generic foreign key and reverse generic relation descriptors."""
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


class _GenericRelatedManager:
    """
    Async manager returned by GenericRelation descriptors.

    Supports ``all()``, ``filter()``, ``count()``, and ``create()``.
    """

    def __init__(self, instance, related_model, ct_field: str, fk_field: str):
        self._instance = instance
        self._related_model = related_model
        self._ct_field = ct_field
        self._fk_field = fk_field

    async def _get_ct_id(self) -> int:
        from buraq.contrib.contenttypes.models import ContentType
        ct = await ContentType.get_for_model(type(self._instance))
        return ct.id

    async def all(self):
        ct_id = await self._get_ct_id()
        return await self._related_model.objects.filter(
            **{self._ct_field: ct_id, self._fk_field: self._instance.pk}
        ).all()

    async def filter(self, **kwargs):
        ct_id = await self._get_ct_id()
        return await self._related_model.objects.filter(
            **{self._ct_field: ct_id, self._fk_field: self._instance.pk, **kwargs}
        ).all()

    async def count(self) -> int:
        ct_id = await self._get_ct_id()
        return await self._related_model.objects.filter(
            **{self._ct_field: ct_id, self._fk_field: self._instance.pk}
        ).count()

    async def create(self, **kwargs):
        ct_id = await self._get_ct_id()
        kwargs[self._ct_field] = ct_id
        kwargs[self._fk_field] = self._instance.pk
        return await self._related_model.objects.create(**kwargs)


class GenericRelation:
    """
    Reverse accessor for ``GenericForeignKey``.

    Declare on the *target* model to get back all objects that point to it
    via a GenericForeignKey.

    Usage::

        class Post(Model):
            comments = GenericRelation(
                "Comment",
                ct_field="content_type_id",
                fk_field="object_id",
            )

        post = await Post.objects.get(id=1)
        comments = await post.comments.all()
        count = await post.comments.count()
        new_comment = await post.comments.create(body="Great!")

    The ``"Comment"`` argument can be either the model class itself or a
    dotted string ``"myapp.models.Comment"`` resolved at access time.
    """

    def __init__(
        self,
        to,
        ct_field: str = "content_type_id",
        fk_field: str = "object_id",
    ):
        self._to = to
        self._ct_field = ct_field
        self._fk_field = fk_field
        self.name: str | None = None

    def __set_name__(self, owner, name: str) -> None:
        self.name = name

    def _resolve_model(self):
        if isinstance(self._to, str):
            parts = self._to.rsplit(".", 1)
            if len(parts) == 2:
                mod = importlib.import_module(parts[0])
                return getattr(mod, parts[1])
            raise ImportError(
                f"GenericRelation: cannot resolve {self._to!r}. "
                "Use 'myapp.models.ModelName' or pass the class directly."
            )
        return self._to

    def __get__(self, instance, owner):
        if instance is None:
            return self
        related_model = self._resolve_model()
        return _GenericRelatedManager(
            instance=instance,
            related_model=related_model,
            ct_field=self._ct_field,
            fk_field=self._fk_field,
        )
