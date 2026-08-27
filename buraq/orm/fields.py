import uuid as _uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

CASCADE = "CASCADE"
PROTECT = "PROTECT"
SET_NULL = "SET_NULL"
DO_NOTHING = "DO_NOTHING"
SET_DEFAULT = "SET_DEFAULT"
RESTRICT = "RESTRICT"

# DB-level variants — identical SQL behaviour to their Python counterparts but signal
# intent: deletions are handled by the database engine, not Python callbacks.
DB_CASCADE = "DB_CASCADE"
DB_SET_NULL = "DB_SET_NULL"
DB_SET_DEFAULT = "DB_SET_DEFAULT"


class Field:
    """Base field — all Buraq fields inherit from this."""

    _sa_type: Any = None

    def __init__(
        self,
        null: bool = False,
        blank: bool = False,
        default: Any = None,
        unique: bool = False,
        db_index: bool = False,
        verbose_name: str = "",
        choices: list = None,
        validators: list = None,
        editable: bool = True,
        help_text: str = "",
    ):
        self.null = null
        self.blank = blank
        self.default = default
        self.unique = unique
        self.db_index = db_index
        self.verbose_name = verbose_name
        self.choices = choices or []
        self.validators = validators or []
        self.editable = editable
        self.help_text = help_text

    def to_sa_column(self, name: str = "") -> sa.Column:
        kwargs: dict[str, Any] = {
            "nullable": self.null,
            "unique": self.unique,
            "index": self.db_index,
        }
        if self.default is not None:
            kwargs["default"] = self.default
        return sa.Column(self._sa_type, **kwargs)


class CharField(Field):
    def __init__(self, max_length: int = 255, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length

    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(
            sa.String(self.max_length),
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class SlugField(CharField):
    def __init__(self, max_length: int = 50, **kwargs):
        super().__init__(max_length=max_length, **kwargs)


class EmailField(CharField):
    def __init__(self, max_length: int = 254, **kwargs):
        super().__init__(max_length=max_length, **kwargs)


class URLField(CharField):
    def __init__(self, max_length: int = 200, **kwargs):
        super().__init__(max_length=max_length, **kwargs)


class FileField(CharField):
    def __init__(self, upload_to: str = "", max_length: int = 100, **kwargs):
        super().__init__(max_length=max_length, **kwargs)
        self.upload_to = upload_to


class ImageField(FileField):
    pass


class IntegerField(Field):
    _sa_type = sa.Integer


class SmallIntegerField(Field):
    _sa_type = sa.SmallInteger


class BigIntegerField(Field):
    _sa_type = sa.BigInteger


class PositiveIntegerField(Field):
    def to_sa_column(self, name: str = "") -> sa.Column:
        constraint_name = f"ck_{name}_positive" if name else None
        return sa.Column(
            sa.Integer,
            (
                sa.CheckConstraint(f"{name} >= 0", name=constraint_name)
                if name else sa.CheckConstraint("value >= 0")
            ),
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class PositiveSmallIntegerField(Field):
    def to_sa_column(self, name: str = "") -> sa.Column:
        constraint_name = f"ck_{name}_positive" if name else None
        return sa.Column(
            sa.SmallInteger,
            (
                sa.CheckConstraint(f"{name} >= 0", name=constraint_name)
                if name else sa.CheckConstraint("value >= 0")
            ),
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class FloatField(Field):
    _sa_type = sa.Float


class DecimalField(Field):
    def __init__(self, max_digits: int = 10, decimal_places: int = 2, **kwargs):
        super().__init__(**kwargs)
        self.max_digits = max_digits
        self.decimal_places = decimal_places

    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(
            sa.Numeric(precision=self.max_digits, scale=self.decimal_places),
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class BooleanField(Field):
    _sa_type = sa.Boolean

    def __init__(self, default: bool = False, **kwargs):
        super().__init__(default=default, **kwargs)


class NullBooleanField(Field):
    _sa_type = sa.Boolean

    def __init__(self, **kwargs):
        super().__init__(null=True, **kwargs)


class TextField(Field):
    def __init__(self, max_length: int = None, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length

    def to_sa_column(self, name: str = "") -> sa.Column:
        col_type = sa.String(self.max_length) if self.max_length else sa.Text
        return sa.Column(
            col_type,
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class DateField(Field):
    _sa_type = sa.Date


class TimeField(Field):
    _sa_type = sa.Time


class JSONField(Field):
    _sa_type = sa.JSON


class BinaryField(Field):
    _sa_type = sa.LargeBinary


class DateTimeField(Field):
    def __init__(self, auto_now: bool = False, auto_now_add: bool = False, **kwargs):
        if auto_now and auto_now_add:
            raise ValueError("DateTimeField cannot have both auto_now=True and auto_now_add=True.")
        super().__init__(**kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add

    def to_sa_column(self, name: str = "") -> sa.Column:
        kwargs: dict[str, Any] = {"nullable": self.null}
        if self.auto_now_add:
            kwargs["default"] = lambda: datetime.now(UTC)
        if self.auto_now:
            kwargs["default"] = lambda: datetime.now(UTC)
            kwargs["onupdate"] = lambda: datetime.now(UTC)
        return sa.Column(sa.DateTime(timezone=True), **kwargs)


class UUIDField(Field):
    def __init__(self, default=None, **kwargs):
        if default is None:
            default = _uuid.uuid4
        super().__init__(default=default, **kwargs)

    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(
            sa.String(36),
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=lambda: str(self.default()) if callable(self.default) else self.default,
        )


class PositiveBigIntegerField(Field):
    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(
            sa.BigInteger,
            sa.CheckConstraint(sa.column(name) >= 0),
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class DurationField(Field):
    """Stores a Python timedelta as a database INTERVAL (or INTEGER microseconds on SQLite)."""

    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(
            sa.Interval,
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class GenericIPAddressField(CharField):
    """Stores IPv4 or IPv6 addresses; max_length 39 covers full IPv6."""

    def __init__(self, protocol: str = "both", **kwargs):
        kwargs.setdefault("max_length", 39)
        super().__init__(**kwargs)
        self.protocol = protocol  # "ipv4", "ipv6", "both"


class AutoField(Field):
    """Explicit primary key field (usually not needed — auto-added as `id`)."""

    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(sa.Integer, primary_key=True, autoincrement=True)


class SmallAutoField(Field):
    """SmallInteger primary key (auto-increment)."""

    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(sa.SmallInteger, primary_key=True, autoincrement=True)


class BigAutoField(Field):
    """BigInteger primary key (auto-increment)."""

    def to_sa_column(self, name: str = "") -> sa.Column:
        return sa.Column(sa.BigInteger, primary_key=True, autoincrement=True)


class FilePathField(CharField):
    """CharField that stores a filesystem path; optionally restricted to a directory."""

    def __init__(self, path: str = "", match: str = None, recursive: bool = False,
                 allow_files: bool = True, allow_folders: bool = False,
                 max_length: int = 100, **kwargs):
        super().__init__(max_length=max_length, **kwargs)
        self.path = path
        self.match = match
        self.recursive = recursive
        self.allow_files = allow_files
        self.allow_folders = allow_folders


class ForeignKey(Field):
    """
    Usage:
        author_id = ForeignKey(User)           # class reference
        author_id = ForeignKey("buraq_users") # string table name
    """

    def __init__(
        self, to: Any, on_delete: str = "CASCADE", null: bool = False,
        related_name: str = "", **kwargs
    ):
        super().__init__(null=null, **kwargs)
        self._to = to
        self.related_name = related_name
        if isinstance(to, str):
            self._ref = f"{to}.id"
        elif hasattr(to, "__tablename__"):
            self._ref = f"{to.__tablename__}.id"
        else:
            self._ref = None  # lazy resolve at column creation

        _ondelete_map = {
            "CASCADE": "CASCADE",
            "DB_CASCADE": "CASCADE",
            "SET_NULL": "SET NULL",
            "DB_SET_NULL": "SET NULL",
            "PROTECT": "RESTRICT",
            "RESTRICT": "RESTRICT",
            "DO_NOTHING": "NO ACTION",
            "SET_DEFAULT": "SET DEFAULT",
            "DB_SET_DEFAULT": "SET DEFAULT",
        }
        self._ondelete = _ondelete_map.get(on_delete.upper(), "CASCADE")

    def to_sa_column(self, name: str = "") -> sa.Column:
        if self._ref is None:
            # Lazy resolve — model class passed but not yet mapped
            if hasattr(self._to, "__tablename__"):
                self._ref = f"{self._to.__tablename__}.id"
            else:
                raise ValueError(f"ForeignKey target {self._to!r} has no __tablename__")
        return sa.Column(
            sa.Integer,
            sa.ForeignKey(self._ref, ondelete=self._ondelete),
            nullable=self.null,
        )


class OneToOneField(ForeignKey):
    """Like ForeignKey but enforces unique constraint."""

    def to_sa_column(self, name: str = "") -> sa.Column:
        if self._ref is None:
            if hasattr(self._to, "__tablename__"):
                self._ref = f"{self._to.__tablename__}.id"
            else:
                raise ValueError(f"OneToOneField target {self._to!r} has no __tablename__")
        return sa.Column(
            sa.Integer,
            sa.ForeignKey(self._ref, ondelete=self._ondelete),
            nullable=self.null,
            unique=True,
        )


class ManyToManyField(Field):
    """
    Declares a many-to-many relationship via an association table.

    Usage:
        class Post(models.Model):
            tags = ManyToManyField("tags")   # string table name
            # or
            tags = ManyToManyField(Tag)      # model class

    Accessing:
        post = await Post.objects.get(id=1)
        tags = await post.tags.all()
        await post.tags.add(tag)
        await post.tags.remove(tag)
        await post.tags.set([tag1, tag2])
        await post.tags.clear()
    """

    def __init__(
        self, to: Any, through: Any = None, related_name: str = "",
        symmetrical: bool = True, **kwargs
    ):
        # ManyToManyField does NOT create a column on the model table
        super().__init__(**kwargs)
        self._to = to
        self.through = through
        self.related_name = related_name
        self.symmetrical = symmetrical
        self._attr_name = None  # set by base.py when attaching

    def to_sa_column(self, name: str = ""):
        # No column on the source table — relationship is managed via association table
        return None

    def contribute_to_class(self, model_cls, attr_name: str):
        """Called by Model.__init_subclass__ to set up the accessor."""
        self._attr_name = attr_name
        self._source_model = model_cls

        to = self._to
        through = self.through

        # Create association table if no through model specified
        if through is None:
            from buraq.core.db import Base
            source_table = model_cls.__tablename__
            target_table = (
                to if isinstance(to, str)
                else getattr(to, "__tablename__", str(to).lower() + "s")
            )
            assoc_table_name = f"{source_table}_{target_table}"

            # Only create if not already defined
            from sqlalchemy import Column, ForeignKey, Integer, Table
            if assoc_table_name not in Base.metadata.tables:
                self._assoc_table = Table(
                    assoc_table_name,
                    Base.metadata,
                    Column(
                        "source_id", Integer,
                        ForeignKey(f"{source_table}.id", ondelete="CASCADE"), primary_key=True,
                    ),
                    Column(
                        "target_id", Integer,
                        ForeignKey(f"{target_table}.id", ondelete="CASCADE"), primary_key=True,
                    ),
                )
            else:
                self._assoc_table = Base.metadata.tables[assoc_table_name]
        else:
            if hasattr(through, "__table__"):
                self._assoc_table = through.__table__
            elif isinstance(through, str):
                from buraq.core.db import Base
                self._assoc_table = Base.metadata.tables.get(through)
            else:
                self._assoc_table = None

        # Attach M2MManager descriptor to model class
        descriptor = _M2MDescriptor(self)
        setattr(model_cls, attr_name, descriptor)


class _M2MDescriptor:
    """Descriptor that returns a _M2MManager bound to a specific instance."""

    def __init__(self, field: ManyToManyField):
        self.field = field

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return _M2MManager(instance, self.field)


class _M2MManager:
    """Provides .all(), .add(), .remove(), .set(), .clear() for M2M relations."""

    def __init__(self, instance, field: ManyToManyField):
        self._instance = instance
        self._field = field

    def all(self):
        """
        The prefetched list if ``prefetch_related(attr_name)`` populated one
        on this instance — plain, already in memory, no query. Otherwise a
        coroutine that fetches it, exactly as before: ``await post.tags.all()``.
        """
        attr_name = self._field._attr_name
        if attr_name:
            cached = getattr(self._instance, f"_prefetched_{attr_name}", None)
            if cached is not None:
                return cached
        return self._fetch_all()

    async def _fetch_all(self) -> list:
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        assoc = self._field._assoc_table
        to = self._field._to
        if isinstance(to, str):
            raise RuntimeError("ManyToManyField target must be a Model class to use .all()")
        async with SessionLocal() as db:
            q = sa.select(to).join(assoc, to.id == assoc.c.target_id).where(
                assoc.c.source_id == self._instance.id
            )
            result = await db.execute(q)
            return list(result.scalars().all())

    async def add(self, *objs) -> None:
        if not objs:
            return
        from buraq.conf import settings
        from buraq.core.db import SessionLocal
        from buraq.signals import m2m_changed
        assoc = self._field._assoc_table
        rows = [{"source_id": self._instance.id, "target_id": obj.id} for obj in objs]
        pk_set = {obj.id for obj in objs}
        target_model = self._field._to if not isinstance(self._field._to, str) else None
        await m2m_changed.send(
            sender=assoc, action="pre_add", instance=self._instance,
            reverse=False, model=target_model, pk_set=pk_set,
        )
        url = settings.DATABASE_URL
        async with SessionLocal() as db:
            try:
                from sqlalchemy.engine import make_url as _make_url
                dialect = _make_url(url).get_dialect().name
            except Exception:
                dialect = "postgresql"
            if dialect == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as _insert
            elif dialect in ("mysql", "mariadb"):
                from sqlalchemy.dialects.mysql import insert as _insert  # type: ignore[no-redef]
            else:
                from sqlalchemy.dialects.postgresql import (
                    insert as _insert,  # type: ignore[no-redef]
                )
            stmt = _insert(assoc).values(rows).on_conflict_do_nothing()
            await db.execute(stmt)
            await db.commit()
        await m2m_changed.send(
            sender=assoc, action="post_add", instance=self._instance,
            reverse=False, model=target_model, pk_set=pk_set,
        )

    async def remove(self, *objs) -> None:
        from buraq.core.db import SessionLocal
        from buraq.signals import m2m_changed
        assoc = self._field._assoc_table
        ids = [obj.id for obj in objs]
        pk_set = set(ids)
        target_model = self._field._to if not isinstance(self._field._to, str) else None
        await m2m_changed.send(
            sender=assoc, action="pre_remove", instance=self._instance,
            reverse=False, model=target_model, pk_set=pk_set,
        )
        async with SessionLocal() as db:
            await db.execute(
                assoc.delete().where(
                    assoc.c.source_id == self._instance.id,
                    assoc.c.target_id.in_(ids),
                )
            )
            await db.commit()
        await m2m_changed.send(
            sender=assoc, action="post_remove", instance=self._instance,
            reverse=False, model=target_model, pk_set=pk_set,
        )

    async def set(self, objs) -> None:
        """Replace all related objects atomically (clear + add in one session)."""
        from buraq.conf import settings
        from buraq.core.db import SessionLocal
        from buraq.signals import m2m_changed
        assoc = self._field._assoc_table
        target_model = self._field._to if not isinstance(self._field._to, str) else None
        rows = [{"source_id": self._instance.id, "target_id": obj.id} for obj in objs]
        pk_set = {obj.id for obj in objs}
        await m2m_changed.send(
            sender=assoc, action="pre_clear", instance=self._instance,
            reverse=False, model=target_model, pk_set=None,
        )
        async with SessionLocal() as db:
            await db.execute(
                assoc.delete().where(assoc.c.source_id == self._instance.id)
            )
            if rows:
                try:
                    from sqlalchemy.engine import make_url as _make_url
                    dialect = _make_url(settings.DATABASE_URL).get_dialect().name
                except Exception:
                    dialect = "postgresql"
                if dialect == "sqlite":
                    from sqlalchemy.dialects.sqlite import insert as _insert
                elif dialect in ("mysql", "mariadb"):
                    from sqlalchemy.dialects.mysql import (
                        insert as _insert,  # type: ignore[no-redef]
                    )
                else:
                    from sqlalchemy.dialects.postgresql import (
                        insert as _insert,  # type: ignore[no-redef]
                    )
                await db.execute(_insert(assoc).values(rows).on_conflict_do_nothing())
            await db.commit()
        await m2m_changed.send(
            sender=assoc, action="post_add", instance=self._instance,
            reverse=False, model=target_model, pk_set=pk_set,
        )

    async def clear(self) -> None:
        from buraq.core.db import SessionLocal
        from buraq.signals import m2m_changed
        assoc = self._field._assoc_table
        target_model = self._field._to if not isinstance(self._field._to, str) else None
        await m2m_changed.send(
            sender=assoc, action="pre_clear", instance=self._instance,
            reverse=False, model=target_model, pk_set=None,
        )
        async with SessionLocal() as db:
            await db.execute(
                assoc.delete().where(assoc.c.source_id == self._instance.id)
            )
            await db.commit()
        await m2m_changed.send(
            sender=assoc, action="post_clear", instance=self._instance,
            reverse=False, model=target_model, pk_set=None,
        )

    async def count(self) -> int:
        from sqlalchemy import func, select

        from buraq.core.db import SessionLocal
        assoc = self._field._assoc_table
        async with SessionLocal() as db:
            result = await db.execute(
                select(func.count()).where(assoc.c.source_id == self._instance.id)
            )
            return result.scalar() or 0


class GeneratedField(Field):
    """
    A read-only field whose value is computed by the database engine.

    The ``expression`` is a raw SQL string (or SQLAlchemy ``text()``/expression)
    evaluated by the database on every INSERT or UPDATE.

    ``db_persist=True`` (default) creates a STORED/PERSISTENT generated column —
    the value is computed once on write and stored alongside the row.  This is
    the most portable option (PostgreSQL 12+, MySQL 5.7+, SQLite 3.31+).

    ``db_persist=False`` creates a VIRTUAL generated column computed on every
    read.  Not supported by all databases (e.g. PostgreSQL does not support
    virtual generated columns).

    Usage::

        class Product(models.Model):
            price      = models.DecimalField(max_digits=10, decimal_places=2)
            tax_rate   = models.FloatField(default=0.2)
            price_incl = GeneratedField(
                expression="price * (1 + tax_rate)",
                output_field=models.DecimalField(max_digits=10, decimal_places=2),
                db_persist=True,
            )

    .. note::
        Generated columns are database-managed and cannot be set in Python.
        Attempting to assign a value to a generated field is a no-op.
    """

    def __init__(self, expression, output_field: Field, db_persist: bool = True, **kwargs):
        kwargs.setdefault("editable", False)
        super().__init__(**kwargs)
        self.expression = expression
        self.output_field = output_field
        self.db_persist = db_persist

    def to_sa_column(self, name: str = "") -> sa.Column:
        out = self.output_field
        sa_type = out._sa_type if out._sa_type is not None else sa.Text()

        # For CharField/similar, resolve type with parameters.
        if isinstance(out, CharField):
            sa_type = sa.String(out.max_length)
        elif isinstance(out, DecimalField):
            sa_type = sa.Numeric(precision=out.max_digits, scale=out.decimal_places)
        elif isinstance(out, IntegerField):
            sa_type = sa.Integer()
        elif isinstance(out, FloatField):
            sa_type = sa.Float()
        elif isinstance(out, BooleanField):
            sa_type = sa.Boolean()

        expr_text = (
            self.expression
            if isinstance(self.expression, str)
            else str(self.expression.compile(compile_kwargs={"literal_binds": True}))
        )
        return sa.Column(
            sa_type,
            sa.Computed(expr_text, persisted=self.db_persist),
            nullable=True,
        )


class CompositePrimaryKey:
    """
    Declares a composite (multi-column) primary key for a model.

    Set ``primary_key`` on the model's ``Meta`` class::

        class OrderItem(models.Model):
            order_id   = models.ForeignKey(Order, on_delete=models.CASCADE)
            product_id = models.ForeignKey(Product, on_delete=models.CASCADE)
            quantity   = models.IntegerField(default=1)

            class Meta:
                primary_key = CompositePrimaryKey("order_id", "product_id")

    The named columns will have ``primary_key=True`` in the generated
    SQLAlchemy table definition and the implicit auto-increment ``id`` column
    will **not** be added.

    .. note::
        Models with a composite primary key do not have an ``id`` attribute.
        Use the individual key columns to look up rows::

            item = await OrderItem.objects.get(order_id=1, product_id=5)
    """

    def __init__(self, *fields: str):
        if len(fields) < 2:
            raise ValueError("CompositePrimaryKey requires at least two field names.")
        self.fields = fields

    def __repr__(self) -> str:
        return f"CompositePrimaryKey({', '.join(repr(f) for f in self.fields)})"

