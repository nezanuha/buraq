"""
Generic content type framework — allows models to have generic foreign keys
pointing at any other installed model.

Usage:
    from buraq.contrib.contenttypes.fields import GenericForeignKey

    class Comment(Model):
        content_type_id = Column(Integer)
        object_id = Column(Integer)
        content_object = GenericForeignKey("content_type_id", "object_id")

    comment = await Comment.objects.get(id=1)
    post = await comment.content_object   # resolves to the linked object
"""
from __future__ import annotations

import sqlalchemy as sa

from buraq.orm.base import Model


class ContentType(Model):
    """Maps app_label + model name to a unique integer ID for generic relations."""

    __tablename__ = "contenttypes_contenttype"
    __table_args__ = (sa.UniqueConstraint("app_label", "model"),)

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    app_label = sa.Column(sa.String(100), nullable=False)
    model = sa.Column(sa.String(100), nullable=False)

    def __repr__(self):
        return f"<ContentType {self.app_label}.{self.model}>"

    @classmethod
    async def get_for_model(cls, model_class) -> "ContentType":
        app_label = model_class.__module__.split(".")[0]
        model_name = model_class.__name__.lower()
        ct, _ = await cls.objects.get_or_create(
            defaults={},
            app_label=app_label,
            model=model_name,
        )
        return ct
