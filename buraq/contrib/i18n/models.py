"""
TranslatableModel — per-language field translations with a companion translation table.

Usage::

    from buraq import models
    from buraq.contrib.i18n.models import TranslatableModel, TranslatedFields

    class Article(TranslatableModel):
        slug = models.SlugField(unique=True)

        translations = TranslatedFields(
            title   = models.CharField(max_length=255),
            content = models.TextField(),
        )

    # In views / tasks
    article = await Article.objects.get(slug="hello")

    # Read
    tr = await article.get_translation("ar")          # ArticleTranslation instance
    title = await article.safe_translation_getter(
        "title", language_code="ar", fallback_language="en"
    )

    # Write
    await article.set_translation("ar", title="مرحبا", content="...")

    # All translations
    translations = await article.get_translations()   # list[ArticleTranslation]
"""
from __future__ import annotations

import sqlalchemy as sa

from buraq.core.db import Base, SessionLocal
from buraq.orm.base import Model
from buraq.orm.fields import Field
from buraq.orm.manager import DoesNotExist, Manager


class TranslatedFields:
    """
    Descriptor that collects field definitions for the auto-generated
    ``{Model}Translation`` table.

    Assign it once as a class attribute; ``TranslatableModel.__init_subclass__``
    picks up the stored definitions and creates the companion table.
    """

    def __init__(self, **fields: Field):
        self._fields: dict[str, Field] = fields
        self._attr_name: str | None = None

    def __set_name__(self, owner, name: str):
        self._attr_name = name
        # Store on owner so __init_subclass__ can find it
        if not hasattr(owner, "_translated_field_defs"):
            owner._translated_field_defs = {}
            owner._translated_attr_name  = name
        owner._translated_field_defs = dict(self._fields)
        owner._translated_attr_name  = name


class TranslatableModel(Model):
    """
    Model base that auto-creates a ``{table}_translation`` companion table.

    Subclass this instead of ``Model`` when some fields need per-language
    values.  The translation table has columns:

    * ``id``            — auto PK
    * ``master_id``     — FK → parent table
    * ``language_code`` — 10-char string (``"en"``, ``"ar"``, …)
    * one column per field declared in ``TranslatedFields``

    A ``UNIQUE(master_id, language_code)`` constraint ensures one translation
    row per language per object.
    """

    __abstract__ = True

    def __init_subclass__(cls, **kwargs):
        # Pull field defs off before super() runs so they don't confuse SQLAlchemy
        raw_defs: dict[str, Field] = dict(getattr(cls, "_translated_field_defs", {}))
        attr_name: str | None      = getattr(cls, "_translated_attr_name", None)

        # Remove the TranslatedFields descriptor from the class dict so that
        # SQLAlchemy's mapper never sees it.
        if attr_name and attr_name in cls.__dict__:
            delattr(cls, attr_name)

        # Call super().__init_subclass__ — sets __tablename__, auto PK, etc.
        super().__init_subclass__(**kwargs)

        # Nothing to do for abstract classes or classes without translated fields
        if not raw_defs or cls.__dict__.get("__abstract__"):
            return

        # ── Build the translation model dynamically ────────────────────────
        master_table = cls.__tablename__
        trans_table  = f"{master_table}_translation"
        trans_name   = f"{cls.__name__}Translation"

        # Convert Field descriptors → sa.Column objects
        translated_cols: dict[str, sa.Column] = {}
        for field_name, field_obj in raw_defs.items():
            col = field_obj.to_sa_column(name=field_name)
            if col is not None:
                # Translation columns are nullable — partial translations are valid.
                col.nullable = True
                translated_cols[field_name] = col

        attrs = {
            "__tablename__": trans_table,
            "id": sa.Column(sa.Integer, primary_key=True, autoincrement=True),
            "master_id": sa.Column(
                sa.Integer,
                sa.ForeignKey(f"{master_table}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            "language_code": sa.Column(sa.String(10), nullable=False),
            "__table_args__": (
                sa.UniqueConstraint(
                    "master_id", "language_code",
                    name=f"uq_{trans_table}_master_lang",
                ),
            ),
            **translated_cols,
        }

        translation_model = type(trans_name, (Base,), attrs)

        # Attach Manager and DoesNotExist to the translation model
        translation_model.objects = Manager(translation_model)
        translation_model.DoesNotExist = type("DoesNotExist", (DoesNotExist,), {
            "__doc__": f"{trans_name} matching query does not exist."
        })

        # Expose on the parent model
        cls.translation_model = translation_model
        cls._translated_field_names = list(translated_cols.keys())

    # ── Instance helpers ───────────────────────────────────────────────────

    async def get_translation(self, language_code: str | None = None):
        """
        Return the translation row for *language_code* (defaults to the
        active language from ``LocaleMiddleware``).

        Raises ``self.translation_model.DoesNotExist`` if not found.
        """
        if language_code is None:
            from buraq.utils.translation import get_language
            language_code = get_language()

        TM = self.__class__.translation_model
        return await TM.objects.get(master_id=self.id, language_code=language_code)

    async def safe_translation_getter(
        self,
        field: str,
        *,
        language_code: str | None = None,
        default=None,
        fallback_language: str | None = None,
    ):
        """
        Return the value of *field* in the given language.

        Falls back to *fallback_language* if the requested translation does
        not exist, then to *default* if neither is found.
        """
        if language_code is None:
            from buraq.utils.translation import get_language
            language_code = get_language()

        TM = self.__class__.translation_model
        try:
            tr = await TM.objects.get(master_id=self.id, language_code=language_code)
            return getattr(tr, field, default)
        except Exception:
            pass

        if fallback_language and fallback_language != language_code:
            try:
                tr = await TM.objects.get(master_id=self.id, language_code=fallback_language)
                return getattr(tr, field, default)
            except Exception:
                pass

        return default

    async def set_translation(self, language_code: str, **fields) -> None:
        """
        Upsert a translation row.  Creates a new row if none exists for
        *language_code*; updates the existing row otherwise.
        """
        TM = self.__class__.translation_model
        async with SessionLocal() as db:
            result = await db.execute(
                sa.select(TM).where(
                    TM.master_id == self.id,
                    TM.language_code == language_code,
                )
            )
            tr = result.scalars().first()
            if tr is None:
                tr = TM(master_id=self.id, language_code=language_code, **fields)
                db.add(tr)
            else:
                for k, v in fields.items():
                    setattr(tr, k, v)
            await db.commit()

    async def get_translations(self) -> list:
        """Return all translation rows for this instance."""
        TM = self.__class__.translation_model
        async with SessionLocal() as db:
            result = await db.execute(
                sa.select(TM).where(TM.master_id == self.id)
            )
            return list(result.scalars().all())

    async def delete_translation(self, language_code: str) -> None:
        """Delete the translation row for *language_code* if it exists."""
        TM = self.__class__.translation_model
        async with SessionLocal() as db:
            result = await db.execute(
                sa.select(TM).where(
                    TM.master_id == self.id,
                    TM.language_code == language_code,
                )
            )
            tr = result.scalars().first()
            if tr:
                await db.delete(tr)
                await db.commit()
