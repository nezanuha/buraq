"""
Enum-based field choices.

Usage:
    from buraq.utils.choices import TextChoices, IntegerChoices

    class Status(TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Priority(IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    # In a model field:
    status = Column(String, default=Status.DRAFT)

    # Choices for a form SelectField:
    choices = Status.choices  # [("draft", "Draft"), ("published", "Published"), ...]
    labels = Status.labels    # ["Draft", "Published", "Archived"]
    values = Status.values    # ["draft", "published", "archived"]
"""
from __future__ import annotations

import enum


class ChoicesMeta(enum.EnumMeta):
    """Metaclass that injects .choices, .labels, .values, .names onto enum classes."""

    def __new__(mcs, classname, bases, classdict, **kwargs):
        labels = {}
        for key in list(classdict._member_names):
            val = classdict[key]
            if isinstance(val, (list, tuple)) and len(val) == 2:
                classdict[key] = val[0]
                labels[key] = val[1]
        cls = super().__new__(mcs, classname, bases, classdict, **kwargs)
        cls._labels_ = labels
        return cls

    @property
    def choices(cls):
        return [(m.value, cls._labels_.get(m.name, m.name)) for m in cls]

    @property
    def labels(cls):
        return [cls._labels_.get(m.name, m.name) for m in cls]

    @property
    def values(cls):
        return [m.value for m in cls]

    @property
    def names(cls):
        return [m.name for m in cls]


class TextChoices(enum.StrEnum, metaclass=ChoicesMeta):
    """String-valued enum with .choices support."""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()


class IntegerChoices(int, enum.Enum, metaclass=ChoicesMeta):
    """Integer-valued enum with .choices support."""
