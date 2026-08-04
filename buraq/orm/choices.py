import enum


class TextChoices(enum.StrEnum):
    @classmethod
    def choices(cls):
        return [(m.value, m.name.replace("_", " ").title()) for m in cls]

    @classmethod
    def values(cls):
        return [m.value for m in cls]


class IntegerChoices(enum.IntEnum):
    @classmethod
    def choices(cls):
        return [(m.value, m.name.replace("_", " ").title()) for m in cls]

    @classmethod
    def values(cls):
        return [m.value for m in cls]
