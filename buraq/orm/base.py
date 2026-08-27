import importlib
import re

import sqlalchemy as sa

from buraq.core.db import Base
from buraq.exceptions import ImproperlyConfigured
from buraq.orm.fields import Field, ManyToManyField
from buraq.orm.manager import DoesNotExist, Manager, _ReverseFKDescriptor
from buraq.orm.options import Options


class _ModelState:
    """Tracks per-instance ORM state (whether the row is new, which db)."""

    __slots__ = ("adding", "db", "fields_cache")

    def __init__(self, adding: bool = True, db: str = "default"):
        self.adding = adding
        self.db = db
        self.fields_cache: dict = {}


def _auto_pk_column() -> sa.Column:
    """
    The implicit ``id`` column, per DEFAULT_AUTO_FIELD.

    Integer runs out at about two billion rows, which is a migration nobody
    enjoys, so a project can choose BigAutoField up front. Resolved on each
    model rather than at import so a settings module read later still applies.
    """
    from buraq.conf import settings

    path = getattr(settings, "DEFAULT_AUTO_FIELD", "") or ""
    if not path:
        return sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    module_path, _, name = path.rpartition(".")
    try:
        field_class = getattr(importlib.import_module(module_path), name)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"DEFAULT_AUTO_FIELD is {path!r}, which could not be imported: {exc}"
        ) from exc
    try:
        return field_class().to_sa_column("id")
    except Exception as exc:
        raise ImproperlyConfigured(
            f"DEFAULT_AUTO_FIELD is {path!r}, which is not an auto field: {exc}"
        ) from exc


def _to_table_name(class_name: str, app_label: str = "") -> str:
    """
    ``PostComment`` in app ``blog`` -> ``blog_post_comments``.

    The app label is part of the name because a model name is not unique across
    a project: two apps may each define ``Post``, and without the prefix both
    claim the same table -- SQLAlchemy rejects the second outright, so the two
    apps cannot be installed together at all.
    """
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower() + "s"
    return f"{app_label}_{name}" if app_label else name


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
        opts = Options(cls, meta)
        cls._meta = opts

        # ── 0. Abstract base models ───────────────────────────────────────
        # No table, no mapper, no manager. Fields are still converted so that
        # SQLAlchemy copies the columns onto concrete subclasses.
        if opts.abstract:
            cls.__abstract__ = True
            own_fks = {}
            for attr_name in list(vars(cls)):
                attr = vars(cls)[attr_name]
                if isinstance(attr, Field) and not isinstance(attr, ManyToManyField):
                    # Converting to a Column discards `_to` / `related_name`, so
                    # record ForeignKeys for subclasses to build reverse
                    # accessors from.
                    if hasattr(attr, "_to") and hasattr(attr, "related_name"):
                        own_fks[attr_name] = attr
                    col = attr.to_sa_column(name=attr_name)
                    if col is not None:
                        setattr(cls, attr_name, col)
            cls.__buraq_fks__ = {**_inherited_fk_fields(cls), **own_fks}
            _apply_legacy_meta_aliases(cls, opts)
            return

        # ── 0b. Proxy models ──────────────────────────────────────────────
        # A proxy shares its parent's table entirely; it exists only to attach
        # different Python behaviour (managers, ordering, verbose names).
        if opts.proxy:
            concrete = _concrete_parent(cls)
            if concrete is None:
                raise TypeError(
                    f"{cls.__name__}: Meta.proxy = True requires a concrete model parent."
                )
            cls.__table__ = concrete.__table__
            cls.__tablename__ = concrete.__tablename__
            opts.concrete_model = concrete
            super().__init_subclass__(**kwargs)
            _attach_managers(cls, opts)
            _apply_legacy_meta_aliases(cls, opts)
            _install_order_helpers(cls, opts, {})
            return

        # ── 1. Auto __tablename__ ──────────────────────────────────────────
        if "__tablename__" not in cls.__dict__:
            cls.__tablename__ = opts.db_table or _to_table_name(cls.__name__, opts.app_label)

        # ── 2. Auto primary key ────────────────────────────────────────────
        # Only when the model declares none of its own. A natural key -- a
        # session's key, a country's ISO code -- is the primary key, and adding
        # an id beside it would make a second, meaningless one.
        declares_pk = any(
            getattr(value, "primary_key", False)
            for value in cls.__dict__.values()
            if isinstance(value, sa.Column)
        )
        if "id" not in cls.__dict__ and not declares_pk:
            cls.id = _auto_pk_column()

        # ── 2b. order_with_respect_to adds an implicit _order column ───────
        if opts.order_with_respect_to and "_order" not in cls.__dict__:
            cls._order = sa.Column(sa.Integer, nullable=True, index=True)
            # The ordering is applied implicitly, so combining the two is
            # rejected rather than letting _order silently win.
            if opts.ordering:
                raise TypeError(
                    f"{cls.__name__}: Meta.order_with_respect_to cannot be combined "
                    f"with Meta.ordering (order_with_respect_to sets ordering to '_order')."
                )
            opts.ordering = ["_order"]

        # ── 3. Collect table args from Meta (constraints, unique_together) ─
        table_args = list(getattr(cls, "__table_args__", None) or [])
        if not isinstance(table_args, list):
            table_args = list(table_args)

        table_kwargs = {}
        if table_args and isinstance(table_args[-1], dict):
            table_kwargs = table_args.pop()

        for fields in opts.unique_together:
            table_args.append(
                sa.UniqueConstraint(*fields, name=f"uq_{cls.__tablename__}_{'_'.join(fields)}")
            )

        for constraint in opts.constraints:
            if isinstance(constraint, UniqueConstraint):
                table_args.append(constraint.as_sa_constraint(cls.__tablename__))
            elif isinstance(constraint, CheckConstraint):
                table_args.append(constraint.as_sa_constraint())
            else:
                table_args.append(constraint)

        if opts.db_table_comment:
            table_kwargs["comment"] = opts.db_table_comment

        # SQLAlchemy requires the options dict to be the final element.
        if table_kwargs:
            cls.__table_args__ = (*table_args, table_kwargs)
        elif table_args:
            cls.__table_args__ = tuple(table_args)

        # ── 4. Convert Field → SQLAlchemy Column (skip ManyToManyField) ──
        m2m_fields = {}
        # FKs inherited from abstract bases are not in vars(cls) yet — SQLAlchemy
        # copies those columns during mapping, which happens after this pass.
        fk_fields = dict(_inherited_fk_fields(cls))
        for attr_name in list(vars(cls)):
            attr = vars(cls)[attr_name]
            if isinstance(attr, ManyToManyField):
                m2m_fields[attr_name] = attr
            elif isinstance(attr, Field):
                # Remember ForeignKeys now: converting to a Column below replaces
                # the Field, so the reverse-accessor pass could not find them
                # afterwards.
                if hasattr(attr, "_to") and hasattr(attr, "related_name"):
                    fk_fields[attr_name] = attr
                col = attr.to_sa_column(name=attr_name)
                if col is not None:
                    setattr(cls, attr_name, col)

        # ── 5. Let SQLAlchemy register the mapper ─────────────────────────
        super().__init_subclass__(**kwargs)

        # ── 6. Apply Meta indexes (after table is registered) ─────────────
        for idx in opts.indexes:
            if isinstance(idx, Index):
                idx.as_sa_index(cls.__tablename__, cls)  # registers with metadata

        # ── 7. Attach managers and exceptions ─────────────────────────────
        _attach_managers(cls, opts)
        cls.DoesNotExist = type("DoesNotExist", (DoesNotExist,), {
            "__doc__": f"{cls.__name__} matching query does not exist."
        })

        # ── 8. Legacy _meta_* aliases (admin reads these) ──────────────────
        _apply_legacy_meta_aliases(cls, opts)

        # ── 9. Set up ManyToManyField descriptors ─────────────────────────
        for attr_name, m2m in m2m_fields.items():
            m2m.contribute_to_class(cls, attr_name)

        # ── 10. Set up reverse FK descriptors on parent models ────────────
        for attr_name, fk in fk_fields.items():
            target = getattr(fk, "_to", None)
            related_name = (
                getattr(fk, "related_name", "")
                or opts.default_related_name
                or f"{cls.__name__.lower()}_set"
            )
            if (
                isinstance(target, type)
                and issubclass(target, Base)
                and not hasattr(target, related_name)
            ):
                descriptor = _ReverseFKDescriptor(cls, attr_name, related_name)
                setattr(target, related_name, descriptor)

        cls.__buraq_fks__ = fk_fields

        # ── 11. order_with_respect_to helper methods ──────────────────────
        _install_order_helpers(cls, opts, fk_fields)


    # ── Class-level helpers ────────────────────────────────────────────────────

    @classmethod
    def from_db(cls, db: str, field_names: list, values: tuple):
        """
        Construct an instance from database row data.

        Sets _state.adding=False and populates
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
        """
        Insert or update this instance. Participates in the current atomic() session if active.
        """
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
        """Run all field-level validators and model-level clean(). Raises ValidationError."""
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
        from sqlalchemy import select

        from buraq.core.db import SessionLocal, _current_session
        from buraq.exceptions import ValidationError

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


def _inherited_fk_fields(cls) -> dict:
    """
    ForeignKey fields declared on abstract ancestors.

    Abstract bases convert their fields to Columns, which drops the `_to` and
    `related_name` metadata, so each records the originals in `__buraq_fks__`
    for concrete subclasses to pick up. Walked base-first so nearer ancestors win.
    """
    merged = {}
    for base in reversed(cls.__mro__[1:]):
        merged.update(vars(base).get("__buraq_fks__") or {})
    return merged


def _concrete_parent(cls):
    """Nearest mapped (non-abstract, non-proxy) ancestor — a proxy's real model."""
    for base in cls.__mro__[1:]:
        if base is Model or not isinstance(base, type):
            continue
        if issubclass(base, Base) and "__table__" in vars(base):
            return base
    return None


def _apply_legacy_meta_aliases(cls, opts):
    """
    Keep the older ``_meta_*`` class attributes working.

    ``buraq.contrib.admin`` reads ``_meta_verbose_name`` / ``_meta_verbose_name_plural``
    directly, and third-party code may too, so these stay as aliases of the new
    ``Model._meta`` options rather than being removed.
    """
    cls._meta_ordering = opts.ordering
    cls._meta_verbose_name = opts.verbose_name
    cls._meta_verbose_name_plural = opts.verbose_name_plural


def _attach_managers(cls, opts):
    """
    Wire up ``objects`` plus ``_default_manager`` / ``_base_manager``.

    Managers the user declared on the class are preserved; ``objects`` is only
    created when no manager was declared at all. ``Meta.default_manager_name``
    and ``Meta.base_manager_name`` select among the declared managers.
    """
    declared = {
        name: value for name, value in vars(cls).items() if isinstance(value, Manager)
    }

    for name, manager in declared.items():
        manager._model = cls
        setattr(cls, name, manager)

    if not declared:
        cls.objects = Manager(cls)
        declared["objects"] = cls.objects

    def _resolve(option_name, configured):
        if configured is None:
            return None
        if configured not in declared:
            raise ValueError(
                f"{cls.__name__}: Meta.{option_name} = {configured!r} does not match any "
                f"manager on the model (found: {', '.join(sorted(declared)) or 'none'})."
            )
        return declared[configured]

    default = _resolve("default_manager_name", opts.default_manager_name)
    base = _resolve("base_manager_name", opts.base_manager_name)

    fallback = declared.get("objects") or next(iter(declared.values()))
    cls._default_manager = default or fallback
    cls._base_manager = base or cls._default_manager
    cls._managers = declared


def _install_order_helpers(cls, opts, fk_fields=None):
    """
    Add ``get_<related>_order`` / ``set_<related>_order`` to the related model and
    ``get_next_in_order`` / ``get_previous_in_order`` to this one.

    Backs ``Meta.order_with_respect_to``.
    """
    field = opts.order_with_respect_to
    if not field:
        return

    related_field = field if field.endswith("_id") else f"{field}_id"
    name = cls.__name__.lower()

    async def get_order(self):
        rows = await cls.objects.filter(**{related_field: self.id}).order_by("_order")
        return [row.id for row in rows]

    async def set_order(self, id_list):
        for position, pk in enumerate(id_list):
            await cls.objects.filter(id=pk, **{related_field: self.id}).update(_order=position)

    async def get_next_in_order(self):
        qs = cls.objects.filter(**{related_field: getattr(self, related_field)})
        return await qs.filter(_order__gt=self._order).order_by("_order").first()

    async def get_previous_in_order(self):
        qs = cls.objects.filter(**{related_field: getattr(self, related_field)})
        return await qs.filter(_order__lt=self._order).order_by("-_order").first()

    cls.get_next_in_order = get_next_in_order
    cls.get_previous_in_order = get_previous_in_order

    # The accessors live on the model being ordered *against*. The FK must come
    # from the pre-conversion field map: by now the attribute is a plain Column
    # and no longer carries `_to`.
    fk = (fk_fields or {}).get(field) or (fk_fields or {}).get(related_field)
    parent = getattr(fk, "_to", None) if fk is not None else None
    if isinstance(parent, type) and issubclass(parent, Base):
        setattr(parent, f"get_{name}_order", get_order)
        setattr(parent, f"set_{name}_order", set_order)
