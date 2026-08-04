"""
Buraq model API — re-exports Model, fields, and constraints.

Usage:
    from buraq import models

    class Post(models.Model):
        title      = models.CharField(max_length=200)
        content    = models.TextField()
        published  = models.BooleanField(default=False)
        author_id  = models.ForeignKey("buraq_users")
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            ordering = ["-created_at"]
            verbose_name = "post"
"""
from buraq.orm.base import CheckConstraint, Index, Model, UniqueConstraint
from buraq.orm.choices import IntegerChoices, TextChoices
from buraq.orm.fields import (
    CASCADE,
    DO_NOTHING,
    PROTECT,
    RESTRICT,
    SET_DEFAULT,
    SET_NULL,
    AutoField,
    BigIntegerField,
    BinaryField,
    # Boolean
    BooleanField,
    # Text
    CharField,
    DateField,
    # Date/time
    DateTimeField,
    DecimalField,
    EmailField,
    # Files
    FileField,
    FloatField,
    # Relations
    ForeignKey,
    ImageField,
    # Numeric
    IntegerField,
    # Other
    JSONField,
    ManyToManyField,
    NullBooleanField,
    OneToOneField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    SlugField,
    SmallIntegerField,
    TextField,
    TimeField,
    URLField,
    UUIDField,
)

__all__ = [
    "Model", "Index", "UniqueConstraint", "CheckConstraint",
    "TextChoices", "IntegerChoices",
    "CASCADE", "PROTECT", "SET_NULL", "DO_NOTHING", "SET_DEFAULT", "RESTRICT",
    "CharField", "SlugField", "EmailField", "URLField", "TextField",
    "IntegerField", "BigIntegerField", "SmallIntegerField",
    "PositiveIntegerField", "PositiveSmallIntegerField",
    "FloatField", "DecimalField",
    "BooleanField", "NullBooleanField",
    "DateTimeField", "DateField", "TimeField",
    "JSONField", "BinaryField", "UUIDField", "AutoField",
    "FileField", "ImageField",
    "ForeignKey", "OneToOneField", "ManyToManyField",
]
