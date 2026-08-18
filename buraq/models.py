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
from buraq.orm.aggregates import Avg, Count, Max, Min, StdDev, Sum, Variance
from buraq.orm.base import CheckConstraint, Index, Model, UniqueConstraint
from buraq.orm.expressions import (
    Case,
    Exists,
    ExpressionWrapper,
    OuterRef,
    Subquery,
    Value,
    When,
)
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
    CompositePrimaryKey,
    DateField,
    # Date/time
    DateTimeField,
    DecimalField,
    DurationField,
    EmailField,
    # Files
    FileField,
    FloatField,
    # Relations
    ForeignKey,
    GeneratedField,
    GenericIPAddressField,
    ImageField,
    # Numeric
    IntegerField,
    # Other
    JSONField,
    ManyToManyField,
    NullBooleanField,
    OneToOneField,
    PositiveBigIntegerField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    SlugField,
    SmallIntegerField,
    TextField,
    TimeField,
    URLField,
    UUIDField,
)
from buraq.orm.prefetch import Prefetch
from buraq.orm.query import F, Q
from buraq.orm.window import (
    CumeDist,
    DenseRank,
    FirstValue,
    Lag,
    LastValue,
    Lead,
    NthValue,
    Ntile,
    PercentRank,
    Rank,
    RowNumber,
    Window,
)
from buraq.utils.choices import IntegerChoices, TextChoices

__all__ = [
    "Model", "Index", "UniqueConstraint", "CheckConstraint",
    "TextChoices", "IntegerChoices",
    "CASCADE", "PROTECT", "SET_NULL", "DO_NOTHING", "SET_DEFAULT", "RESTRICT",
    "CharField", "SlugField", "EmailField", "URLField", "TextField",
    "IntegerField", "BigIntegerField", "SmallIntegerField",
    "PositiveIntegerField", "PositiveSmallIntegerField", "PositiveBigIntegerField",
    "FloatField", "DecimalField",
    "BooleanField", "NullBooleanField",
    "DateTimeField", "DateField", "TimeField", "DurationField",
    "JSONField", "BinaryField", "UUIDField", "AutoField",
    "FileField", "ImageField",
    "GenericIPAddressField",
    "ForeignKey", "OneToOneField", "ManyToManyField",
    "GeneratedField", "CompositePrimaryKey",
    "Prefetch",
    # Query expressions, so `models.Q(...)`, `models.F(...)` and
    # `models.Count(...)` are available from this one namespace.
    "F", "Q",
    "Case", "When", "Value", "OuterRef", "Subquery", "Exists", "ExpressionWrapper",
    # Aggregates
    "Count", "Sum", "Avg", "Min", "Max", "StdDev", "Variance",
    # Window functions
    "Window", "RowNumber", "Rank", "DenseRank", "Ntile", "Lag", "Lead",
    "FirstValue", "LastValue", "NthValue", "CumeDist", "PercentRank",
]
