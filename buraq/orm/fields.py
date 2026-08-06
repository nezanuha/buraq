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
    def to_sa_column(self, name: str = "value") -> sa.Column:
        return sa.Column(
            sa.Integer,
            sa.CheckConstraint(f"{name} >= 0"),
            nullable=self.null,
            unique=self.unique,
            index=self.db_index,
            default=self.default,
        )


class PositiveSmallIntegerField(Field):
    _sa_type = sa.SmallInteger


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
    def to_sa_column(self, name: str = "value") -> sa.Column:
        return sa.Column(
            sa.BigInteger,
            sa.CheckConstraint(f"{name} >= 0"),
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

    async def all(self) -> list:
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
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        assoc = self._field._assoc_table
        async with SessionLocal() as db:
            for obj in objs:
                # Check existence before insert to stay dialect-agnostic.
                exists = await db.execute(
                    sa.select(assoc.c.source_id).where(
                        assoc.c.source_id == self._instance.id,
                        assoc.c.target_id == obj.id,
                    ).limit(1)
                )
                if exists.scalar() is None:
                    await db.execute(
                        assoc.insert().values(
                            source_id=self._instance.id,
                            target_id=obj.id,
                        )
                    )
            await db.commit()

    async def remove(self, *objs) -> None:

        from buraq.core.db import SessionLocal
        assoc = self._field._assoc_table
        ids = [obj.id for obj in objs]
        async with SessionLocal() as db:
            await db.execute(
                assoc.delete().where(
                    assoc.c.source_id == self._instance.id,
                    assoc.c.target_id.in_(ids),
                )
            )
            await db.commit()

    async def set(self, objs) -> None:
        await self.clear()
        await self.add(*objs)

    async def clear(self) -> None:
        from buraq.core.db import SessionLocal
        assoc = self._field._assoc_table
        async with SessionLocal() as db:
            await db.execute(
                assoc.delete().where(assoc.c.source_id == self._instance.id)
            )
            await db.commit()

    async def count(self) -> int:
        from sqlalchemy import func, select

        from buraq.core.db import SessionLocal
        assoc = self._field._assoc_table
        async with SessionLocal() as db:
            result = await db.execute(
                select(func.count()).where(assoc.c.source_id == self._instance.id)
            )
            return result.scalar() or 0

