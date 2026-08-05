"""
Database functions — date/time, string, math, null-handling, type, hash.

Usage:
    from buraq.orm import functions as F

    qs = await Post.objects.annotate(year=F.ExtractYear("created_at"))
    qs = await Post.objects.annotate(title_upper=F.Upper("title"))
    qs = await Post.objects.annotate(name=F.Coalesce("nickname", "username"))
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import func


class _DBFunc:
    """Base class for single-column database functions."""

    def __init__(self, field: str):
        self.field = field

    def resolve(self, model) -> sa.sql.ColumnElement:
        col = getattr(model, self.field)
        return self._apply(col)

    def _apply(self, col) -> sa.sql.ColumnElement:
        raise NotImplementedError


class _MultiField:
    """Base class for functions that accept multiple field names or literals."""

    def __init__(self, *fields):
        self.fields = fields

    def _resolve_arg(self, model, arg):
        if isinstance(arg, str):
            col = getattr(model, arg, None)
            if col is not None:
                return col
            return sa.literal(arg)
        if hasattr(arg, "resolve"):
            return arg.resolve(model)
        return sa.literal(arg)

    def resolve(self, model) -> sa.sql.ColumnElement:
        cols = [self._resolve_arg(model, f) for f in self.fields]
        return self._apply(*cols)

    def _apply(self, *cols) -> sa.sql.ColumnElement:
        raise NotImplementedError


# ── Date / Time ──────────────────────────────────────────────────────────────

class Now(_DBFunc):
    def __init__(self):
        pass

    def resolve(self, model):
        return func.now()


class TruncDate(_DBFunc):
    def _apply(self, col):
        return sa.cast(col, sa.Date)


class TruncHour(_DBFunc):
    def _apply(self, col):
        return func.date_trunc("hour", col)


class TruncDay(_DBFunc):
    def _apply(self, col):
        return func.date_trunc("day", col)


class TruncWeek(_DBFunc):
    def _apply(self, col):
        return func.date_trunc("week", col)


class TruncMonth(_DBFunc):
    def _apply(self, col):
        return func.date_trunc("month", col)


class TruncQuarter(_DBFunc):
    def _apply(self, col):
        return func.date_trunc("quarter", col)


class TruncYear(_DBFunc):
    def _apply(self, col):
        return func.date_trunc("year", col)


class ExtractYear(_DBFunc):
    def _apply(self, col): return sa.extract("year", col)


class ExtractMonth(_DBFunc):
    def _apply(self, col): return sa.extract("month", col)


class ExtractDay(_DBFunc):
    def _apply(self, col): return sa.extract("day", col)


class ExtractHour(_DBFunc):
    def _apply(self, col): return sa.extract("hour", col)


class ExtractMinute(_DBFunc):
    def _apply(self, col): return sa.extract("minute", col)


class ExtractSecond(_DBFunc):
    def _apply(self, col): return sa.extract("second", col)


class ExtractWeek(_DBFunc):
    def _apply(self, col): return sa.extract("week", col)


class ExtractWeekDay(_DBFunc):
    def _apply(self, col): return sa.extract("dow", col)


class ExtractQuarter(_DBFunc):
    def _apply(self, col): return sa.extract("quarter", col)


# ── String ────────────────────────────────────────────────────────────────────

class Concat(_MultiField):
    def _apply(self, *cols):
        result = cols[0]
        for col in cols[1:]:
            result = result.concat(col)
        return result


class Length(_DBFunc):
    def _apply(self, col): return func.length(col)


class Upper(_DBFunc):
    def _apply(self, col): return func.upper(col)


class Lower(_DBFunc):
    def _apply(self, col): return func.lower(col)


class Trim(_DBFunc):
    def _apply(self, col): return func.trim(col)


class LTrim(_DBFunc):
    def _apply(self, col): return func.ltrim(col)


class RTrim(_DBFunc):
    def _apply(self, col): return func.rtrim(col)


class Reverse(_DBFunc):
    def _apply(self, col): return func.reverse(col)


class Chr(_DBFunc):
    def _apply(self, col): return func.chr(col)


class Ord(_DBFunc):
    def _apply(self, col): return func.ascii(col)


class Replace(_MultiField):
    """Replace(field, old, new)"""
    def _apply(self, col, old, new):
        return func.replace(col, old, new)


class Substr(_MultiField):
    """Substr(field, pos, length=None)"""
    def _apply(self, col, pos, length=None):
        if length is not None:
            return func.substr(col, pos, length)
        return func.substr(col, pos)

    def resolve(self, model):
        args = [self._resolve_arg(model, f) for f in self.fields]
        return self._apply(*args)


class Left(_MultiField):
    """Left(field, length)"""
    def _apply(self, col, length): return func.left(col, length)


class Right(_MultiField):
    """Right(field, length)"""
    def _apply(self, col, length): return func.right(col, length)


class Repeat(_MultiField):
    """Repeat(field, count)"""
    def _apply(self, col, count): return func.repeat(col, count)


class StrIndex(_MultiField):
    """StrIndex(string, substring)"""
    def _apply(self, col, sub): return func.strpos(col, sub)


class LPad(_MultiField):
    """LPad(field, length, fill)"""
    def _apply(self, col, length, fill): return func.lpad(col, length, fill)


class RPad(_MultiField):
    """RPad(field, length, fill)"""
    def _apply(self, col, length, fill): return func.rpad(col, length, fill)


# ── Math ──────────────────────────────────────────────────────────────────────

class Abs(_DBFunc):
    def _apply(self, col): return func.abs(col)


class Ceil(_DBFunc):
    def _apply(self, col): return func.ceil(col)


class Floor(_DBFunc):
    def _apply(self, col): return func.floor(col)


class Round(_DBFunc):
    def __init__(self, field: str, precision: int = 0):
        super().__init__(field)
        self.precision = precision

    def _apply(self, col): return func.round(col, self.precision)


class Sign(_DBFunc):
    def _apply(self, col): return func.sign(col)


class Sqrt(_DBFunc):
    def _apply(self, col): return func.sqrt(col)


class Log(_DBFunc):
    def __init__(self, field: str, base: float = 10):
        super().__init__(field)
        self.base = base

    def _apply(self, col): return func.log(self.base, col)


class Ln(_DBFunc):
    def _apply(self, col): return func.ln(col)


class Mod(_MultiField):
    """Mod(field, divisor)"""
    def _apply(self, col, divisor): return func.mod(col, divisor)


class Power(_MultiField):
    """Power(field, exponent)"""
    def _apply(self, col, exp): return func.power(col, exp)


class Random(_DBFunc):
    def __init__(self):
        pass

    def resolve(self, model):
        return func.random()


class ACos(_DBFunc):
    def _apply(self, col): return func.acos(col)


class ASin(_DBFunc):
    def _apply(self, col): return func.asin(col)


class ATan(_DBFunc):
    def _apply(self, col): return func.atan(col)


class ATan2(_MultiField):
    """ATan2(y_field, x_field)"""
    def _apply(self, y, x): return func.atan2(y, x)


class Cos(_DBFunc):
    def _apply(self, col): return func.cos(col)


class Degrees(_DBFunc):
    def _apply(self, col): return func.degrees(col)


class Radians(_DBFunc):
    def _apply(self, col): return func.radians(col)


class Sin(_DBFunc):
    def _apply(self, col): return func.sin(col)


class Tan(_DBFunc):
    def _apply(self, col): return func.tan(col)


# ── NULL handling ─────────────────────────────────────────────────────────────

class Coalesce(_MultiField):
    """Return first non-NULL value among fields/literals."""
    def _apply(self, *cols): return func.coalesce(*cols)


class NullIf(_MultiField):
    """Return NULL if field equals value, else field."""
    def _apply(self, col, val): return func.nullif(col, val)


class Greatest(_MultiField):
    def _apply(self, *cols): return func.greatest(*cols)


class Least(_MultiField):
    def _apply(self, *cols): return func.least(*cols)


# ── Type ──────────────────────────────────────────────────────────────────────

_TYPE_MAP = {
    "int": sa.Integer,
    "integer": sa.Integer,
    "text": sa.Text,
    "varchar": sa.String,
    "string": sa.String,
    "float": sa.Float,
    "decimal": sa.Numeric,
    "numeric": sa.Numeric,
    "bool": sa.Boolean,
    "boolean": sa.Boolean,
    "date": sa.Date,
    "datetime": sa.DateTime,
    "timestamp": sa.DateTime,
    "time": sa.Time,
    "uuid": sa.Uuid,
    "json": sa.JSON,
}


class Cast(_DBFunc):
    """Cast(field, output_field)  — output_field is a string type name."""

    def __init__(self, field: str, output_field: str | sa.types.TypeEngine):
        super().__init__(field)
        if isinstance(output_field, str):
            sa_type = _TYPE_MAP.get(output_field.lower(), sa.Text)
            self.sa_type = sa_type()
        else:
            self.sa_type = output_field

    def _apply(self, col): return sa.cast(col, self.sa_type)


# ── Hash ──────────────────────────────────────────────────────────────────────

class MD5(_DBFunc):
    def _apply(self, col): return func.md5(col)


class SHA1(_DBFunc):
    def _apply(self, col): return func.sha1(col)


class SHA256(_DBFunc):
    def _apply(self, col): return func.sha256(col)


class SHA512(_DBFunc):
    def _apply(self, col): return func.sha512(col)


__all__ = [
    # Date/Time
    "Now", "TruncDate", "TruncHour", "TruncDay", "TruncWeek",
    "TruncMonth", "TruncQuarter", "TruncYear",
    "ExtractYear", "ExtractMonth", "ExtractDay", "ExtractHour",
    "ExtractMinute", "ExtractSecond", "ExtractWeek", "ExtractWeekDay", "ExtractQuarter",
    # String
    "Concat", "Length", "Upper", "Lower", "Trim", "LTrim", "RTrim",
    "Replace", "Substr", "Left", "Right", "Repeat", "Reverse",
    "StrIndex", "Chr", "Ord", "LPad", "RPad",
    # Math
    "Abs", "Ceil", "Floor", "Round", "Sign", "Sqrt", "Log", "Ln",
    "Mod", "Power", "Random",
    "ACos", "ASin", "ATan", "ATan2", "Cos", "Degrees", "Radians", "Sin", "Tan",
    # NULL
    "Coalesce", "NullIf", "Greatest", "Least",
    # Type
    "Cast",
    # Hash
    "MD5", "SHA1", "SHA256", "SHA512",
]
