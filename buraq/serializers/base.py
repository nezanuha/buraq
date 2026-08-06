from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal


class SerializationError(Exception):
    pass


class DeserializationError(Exception):
    pass


def _model_fields(obj) -> dict:
    table = getattr(obj.__class__, "__table__", None)
    if table is None:
        raise SerializationError(f"{obj!r} has no __table__ — not a Buraq model.")
    return {col.name: getattr(obj, col.name) for col in table.columns}


def _coerce(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _to_record(obj) -> dict:
    fields = _model_fields(obj)
    return {
        "model": f"{obj.__class__.__module__}.{obj.__class__.__name__}",
        "pk": fields.get("id"),
        "fields": {k: _coerce(v) for k, v in fields.items()},
    }


class BaseSerializer:
    async def serialize(self, queryset, *, indent=None) -> str:
        raise NotImplementedError

    def deserialize(self, data: str):
        raise NotImplementedError
