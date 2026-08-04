import re

import sqlalchemy as sa

from buraq.core.db import Base
from buraq.orm.fields import Field, ManyToManyField
from buraq.orm.manager import DoesNotExist, Manager


def _to_table_name(class_name: str) -> str:
    """PostComment → post_comments"""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower() + "s"


class Index:
    """
    Declare a database index via Meta.indexes.

    Usage:
        class Meta:
            indexes = [
                Index(fields=["title"]),
                Index(fields=["author_id", "created_at"], name="post_author_date_idx"),
            ]
    """

    def __init__(self, fields: list, name: str = "", unique: bool = False):
        self.fields = fields
        self.name = name
        self.unique = unique

    def as_sa_index(self, table_name: str, model_cls) -> sa.Index:
        name = self.name or f"idx_{table_name}_{'_'.join(self.fields)}"
        cols = [getattr(model_cls, f) for f in self.fields]
        return sa.Index(name, *cols, unique=self.unique)


class UniqueConstraint:
    """
    Declare a multi-column unique constraint.

    Usage:
        class Meta:
            constraints = [
                UniqueConstraint(fields=["author_id", "title"], name="unique_author_title"),
            ]
    """

    def __init__(self, fields: list, name: str = ""):
        self.fields = fields
        self.name = name

    def as_sa_constraint(self, table_name: str) -> sa.UniqueConstraint:
        name = self.name or f"uq_{table_name}_{'_'.join(self.fields)}"
        return sa.UniqueConstraint(*self.fields, name=name)


class CheckConstraint:
    """
    Declare a check constraint.

    Usage:
        class Meta:
            constraints = [
                CheckConstraint(check="views >= 0", name="positive_views"),
            ]
    """

    def __init__(self, check: str, name: str = ""):
        self.check = check
        self.name = name

    def as_sa_constraint(self) -> sa.CheckConstraint:
        return sa.CheckConstraint(self.check, name=self.name or None)


class Model(Base):
    """
    Django-like model base. Define fields as class attributes.

    Example:
        from buraq import models

        class Post(models.Model):
            title      = models.CharField(max_length=200)
            content    = models.TextField()
            published  = models.BooleanField(default=False)
            author_id  = models.ForeignKey("buraq_users")
            created_at = models.DateTimeField(auto_now_add=True)

            class Meta:
                ordering = ["-created_at"]
                verbose_name = "blog post"
                verbose_name_plural = "blog posts"
                unique_together = [["author_id", "title"]]
                indexes = [models.Index(fields=["title"])]

    Query:
        posts = await Post.objects.all()
        post  = await Post.objects.get(id=1)
        posts = await Post.objects.filter(Q(published=True) | Q(author_id=1))
        result = await Post.objects.aggregate(total=Count("id"))
    """

    __abstract__ = True

    def __init_subclass__(cls, **kwargs):
        meta = cls.__dict__.get("Meta")

        # ── 1. Auto __tablename__ ──────────────────────────────────────────
        if "__tablename__" not in cls.__dict__:
            cls.__tablename__ = (
                getattr(meta, "table_name", None)
                or getattr(meta, "db_table", None)
                or _to_table_name(cls.__name__)
            )

        # ── 2. Auto primary key ────────────────────────────────────────────
        if "id" not in cls.__dict__:
            cls.id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

        # ── 3. Collect table args from Meta (constraints, unique_together) ─
        table_args = list(getattr(cls, "__table_args__", None) or [])
        if not isinstance(table_args, list):
            table_args = list(table_args)

        if meta:
            # unique_together → UniqueConstraint
            for fields in getattr(meta, "unique_together", []):
                table_args.append(
                    sa.UniqueConstraint(*fields, name=f"uq_{cls.__tablename__}_{'_'.join(fields)}")
                )
            # constraints
            for constraint in getattr(meta, "constraints", []):
                if isinstance(constraint, (UniqueConstraint, CheckConstraint)):
                    if isinstance(constraint, UniqueConstraint):
                        table_args.append(constraint.as_sa_constraint(cls.__tablename__))
                    else:
                        table_args.append(constraint.as_sa_constraint())
                else:
                    table_args.append(constraint)

        if table_args:
            cls.__table_args__ = tuple(table_args)

        # ── 4. Convert Field → SQLAlchemy Column (skip ManyToManyField) ──
        m2m_fields = {}
        for attr_name in list(vars(cls)):
            attr = vars(cls)[attr_name]
            if isinstance(attr, ManyToManyField):
                m2m_fields[attr_name] = attr
            elif isinstance(attr, Field):
                col = attr.to_sa_column(name=attr_name)
                if col is not None:
                    setattr(cls, attr_name, col)
                else:
                    delattr(cls, attr_name)  # remove None columns

        # ── 5. Let SQLAlchemy register the mapper ─────────────────────────
        super().__init_subclass__(**kwargs)

        # ── 6. Apply Meta indexes (after table is registered) ─────────────
        if meta:
            for idx in getattr(meta, "indexes", []):
                if isinstance(idx, Index):
                    idx.as_sa_index(cls.__tablename__, cls)  # registers with metadata

        # ── 7. Attach ORM manager and exceptions ──────────────────────────
        cls.objects = Manager(cls)
        cls.DoesNotExist = type("DoesNotExist", (DoesNotExist,), {
            "__doc__": f"{cls.__name__} matching query does not exist."
        })

        # ── 8. Store Meta options on class ────────────────────────────────
        cls._meta_ordering = getattr(meta, "ordering", [])
        cls._meta_verbose_name = getattr(meta, "verbose_name", cls.__name__.lower())
        cls._meta_verbose_name_plural = getattr(
            meta, "verbose_name_plural", cls._meta_verbose_name + "s"
        )

        # ── 9. Set up ManyToManyField descriptors ─────────────────────────
        for attr_name, m2m in m2m_fields.items():
            m2m.contribute_to_class(cls, attr_name)

    # ── Instance methods (like Django's Model.save/delete) ─────────────────

    async def save(self, update_fields: list = None) -> None:
        """Insert or update this instance."""
        from buraq.core.db import SessionLocal
        from buraq.signals import post_save, pre_save
        created = self.id is None
        await pre_save.send(sender=self.__class__, instance=self, created=created)
        async with SessionLocal() as db:
            if self.id is None:
                db.add(self)
                await db.commit()
                await db.refresh(self)
            else:
                merged = await db.merge(self)
                if update_fields:
                    for field in update_fields:
                        setattr(merged, field, getattr(self, field))
                await db.commit()
                await db.refresh(merged)
                # Sync id back
                self.id = merged.id
        await post_save.send(sender=self.__class__, instance=self, created=created)

    async def delete(self) -> None:
        """Delete this instance from the database."""
        from buraq.core.db import SessionLocal
        from buraq.signals import post_delete, pre_delete
        await pre_delete.send(sender=self.__class__, instance=self)
        async with SessionLocal() as db:
            obj = await db.get(self.__class__, self.id)
            if obj:
                await db.delete(obj)
                await db.commit()
        await post_delete.send(sender=self.__class__, instance=self)

    async def refresh_from_db(self, fields: list = None) -> None:
        """Reload this instance's fields from the database."""
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            fresh = await db.get(self.__class__, self.id)
            if fresh is None:
                raise self.DoesNotExist(
                    f"{self.__class__.__name__} with id={self.id} does not exist."
                )
            for col in self.__class__.__table__.columns:
                setattr(self, col.name, getattr(fresh, col.name))

    def __repr__(self) -> str:
        pk = getattr(self, "id", None)
        if hasattr(self, "__str__") and self.__class__.__str__ is not Model.__str__:
            return f"<{self.__class__.__name__}: {self}>"
        return f"<{self.__class__.__name__} id={pk}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} object ({self.id})"
