import re

import sqlalchemy as sa

from buraq.core.db import Base
from buraq.orm.fields import Field, ManyToManyField
from buraq.orm.manager import DoesNotExist, Manager, _ReverseFKDescriptor


class _ModelState:
    """Mirrors Django's Model._state — tracks per-instance ORM state."""

    __slots__ = ("adding", "db", "fields_cache")

    def __init__(self, adding: bool = True, db: str = "default"):
        self.adding = adding
        self.db = db
        self.fields_cache: dict = {}


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
    Model base class. Define fields as class attributes.

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

        # ── 10. Set up reverse FK descriptors on parent models ────────────
        for attr_name in list(vars(cls)):
            attr = vars(cls)[attr_name]
            if isinstance(attr, Field) and hasattr(attr, "_to") and hasattr(attr, "related_name"):
                # ForeignKey field — register a reverse accessor on the parent model
                target = getattr(attr, "_to", None)
                related_name = getattr(attr, "related_name", "") or f"{cls.__name__.lower()}_set"
                if target and isinstance(target, type) and issubclass(target, Base):
                    fk_field = attr_name
                    child_cls = cls
                    descriptor = _ReverseFKDescriptor(child_cls, fk_field, related_name)
                    if not hasattr(target, related_name):
                        setattr(target, related_name, descriptor)

    # ── Class-level helpers ────────────────────────────────────────────────────

    @classmethod
    def from_db(cls, db: str, field_names: list, values: tuple):
        """
        Construct an instance from database row data.

        Mirrors Django's Model.from_db() — sets _state.adding=False and populates
        _state.fields_cache with the loaded values.
        """
        kwargs = dict(zip(field_names, values, strict=False))
        instance = cls(**kwargs)
        instance._state.adding = False
        instance._state.db = db
        instance._state.fields_cache = dict(kwargs)
        return instance

    def get_deferred_fields(self) -> set:
        """Return the set of field names that have NOT been loaded from the database."""
        all_fields = {c.name for c in self.__class__.__table__.columns}
        loaded = set(self._state.fields_cache.keys()) if self._state.fields_cache else all_fields
        return all_fields - loaded

    async def validate_constraints(self, exclude: list | None = None) -> None:
        """Check all model constraints (unique, check). Raises ValidationError on failure."""
        await self.validate_unique()

    def get_absolute_url(self) -> str:
        """Return the canonical URL for this object. Override in subclasses."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not define get_absolute_url()."
        )

    def natural_key(self) -> tuple:
        """Return a tuple of field values that uniquely identify this object naturally (no PK)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not define natural_key()."
        )

    # ── pk alias ──────────────────────────────────────────────────────────────

    @property
    def pk(self):
        return self.id

    @pk.setter
    def pk(self, value):
        self.id = value

    # ── Instance methods ──────────────────────────────────────────────────────

    def __init__(self, **kwargs):
        from buraq.signals import post_init, pre_init
        pre_init.send_sync(sender=self.__class__, args=(), kwargs=kwargs)
        self._state = _ModelState(adding=True)
        super().__init__(**kwargs)
        post_init.send_sync(sender=self.__class__, instance=self)

    async def save(self, update_fields: list | None = None) -> None:
        """Insert or update this instance. Participates in the current atomic() session if active."""
        from buraq.core.db import SessionLocal, _current_session
        from buraq.signals import post_save, pre_save
        created = self.id is None
        await pre_save.send(sender=self.__class__, instance=self, created=created)

        active_session = _current_session.get()
        if active_session is not None:
            # Use the session from the enclosing atomic() block
            db = active_session
            if self.id is None:
                db.add(self)
                await db.flush()
                await db.refresh(self)
            else:
                merged = await db.merge(self)
                if update_fields:
                    for field in update_fields:
                        setattr(merged, field, getattr(self, field))
                await db.flush()
                await db.refresh(merged)
                for col in self.__class__.__table__.columns:
                    setattr(self, col.name, getattr(merged, col.name))
        else:
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
                    for col in self.__class__.__table__.columns:
                        setattr(self, col.name, getattr(merged, col.name))

        await post_save.send(sender=self.__class__, instance=self, created=created)

    async def delete(self) -> None:
        """Delete this instance from the database."""
        from buraq.core.db import SessionLocal, _current_session
        from buraq.signals import post_delete, pre_delete
        await pre_delete.send(sender=self.__class__, instance=self)
        active = _current_session.get()
        if active is not None:
            obj = await active.get(self.__class__, self.id)
            if obj:
                await active.delete(obj)
                await active.flush()
        else:
            async with SessionLocal() as db:
                obj = await db.get(self.__class__, self.id)
                if obj:
                    await db.delete(obj)
                    await db.commit()
        await post_delete.send(sender=self.__class__, instance=self)

    async def refresh_from_db(self, fields: list | None = None) -> None:
        """Reload this instance's fields from the database."""
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            fresh = await db.get(self.__class__, self.id)
            if fresh is None:
                raise self.DoesNotExist(
                    f"{self.__class__.__name__} with id={self.id} does not exist."
                )
            columns = (
                [c for c in self.__class__.__table__.columns if c.name in fields]
                if fields
                else self.__class__.__table__.columns
            )
            for col in columns:
                setattr(self, col.name, getattr(fresh, col.name))

    async def full_clean(self) -> None:
        """Run all field-level validators and model-level clean(). Raises ValidationError on failure."""
        from buraq.exceptions import ValidationError
        errors: dict[str, list] = {}

        await self.clean_fields(errors)

        try:
            await self.clean()
        except ValidationError as e:
            errors.setdefault("__all__", []).append(str(e))

        try:
            await self.validate_unique()
        except ValidationError as e:
            errors.setdefault("__all__", []).append(str(e))

        if errors:
            raise ValidationError(errors)

    async def clean_fields(self, errors: dict | None = None) -> None:
        """Validate each field's validators. Populates errors dict or raises ValidationError."""
        from buraq.exceptions import ValidationError
        _errors = errors if errors is not None else {}
        for col in self.__class__.__table__.columns:
            val = getattr(self, col.name, None)
            if val is None and not col.nullable and col.default is None and not col.primary_key:
                _errors.setdefault(col.name, []).append("This field cannot be null.")
        if errors is None and _errors:
            raise ValidationError(_errors)

    async def clean(self) -> None:
        """Override to add cross-field model validation. Raise ValidationError on failure."""

    async def validate_unique(self) -> None:
        """Check that unique constraints are not violated. Raises ValidationError if they are."""
        from buraq.core.db import SessionLocal, _current_session
        from buraq.exceptions import ValidationError
        from sqlalchemy import select

        errors = []
        table = self.__class__.__table__
        unique_cols = [c for c in table.columns if c.unique and not c.primary_key]

        async def _run(db):
            for col in unique_cols:
                val = getattr(self, col.name, None)
                if val is None:
                    continue
                q = select(self.__class__).where(
                    getattr(self.__class__, col.name) == val
                )
                if self.id is not None:
                    q = q.where(self.__class__.id != self.id)
                result = await db.execute(q.limit(1))
                if result.scalar_one_or_none() is not None:
                    errors.append(f"{col.name}: Value '{val}' must be unique.")

        active = _current_session.get()
        if active is not None:
            await _run(active)
        else:
            async with SessionLocal() as db:
                await _run(db)

        if errors:
            raise ValidationError("; ".join(errors))

    def __repr__(self) -> str:
        pk = getattr(self, "id", None)
        if hasattr(self, "__str__") and self.__class__.__str__ is not Model.__str__:
            return f"<{self.__class__.__name__}: {self}>"
        return f"<{self.__class__.__name__} id={pk}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} object ({self.id})"
