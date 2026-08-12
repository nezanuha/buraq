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
    async def get_for_model(cls, model_class) -> ContentType:
        app_label = model_class.__module__.split(".")[0]
        model_name = model_class.__name__.lower()
        ct, _ = await cls.objects.get_or_create(
            defaults={},
            app_label=app_label,
            model=model_name,
        )
        return ct

    @classmethod
    async def get_by_natural_key(cls, app_label: str, model: str) -> ContentType:
        """Look up a ContentType by its natural key (app_label, model)."""
        ct = await cls.objects.get_or_none(app_label=app_label, model=model)
        if ct is None:
            raise cls.DoesNotExist(
                f"ContentType matching (app_label={app_label!r}, model={model!r}) not found."
            )
        return ct

    def model_class(self):
        """
        Return the Python class for this ContentType, or None if not importable.

        Searches all installed app modules for a class whose name matches
        ``self.model`` (case-insensitive) and whose module starts with
        ``self.app_label``.
        """
        import importlib
        try:
            from buraq.conf import settings
            installed = getattr(settings, "INSTALLED_APPS", [])
        except Exception:
            installed = []

        for app in installed:
            if not app.startswith(self.app_label):
                continue
            for mod_name in (f"{app}.models", app):
                try:
                    mod = importlib.import_module(mod_name)
                    for attr in dir(mod):
                        obj = getattr(mod, attr, None)
                        if (
                            isinstance(obj, type)
                            and attr.lower() == self.model.lower()
                        ):
                            return obj
                except ImportError:
                    continue
        return None
