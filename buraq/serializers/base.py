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

    def deserialize(self, data: str) -> list[dict]:
        """
        Parse serialized data and return a list of record dicts.

        Each dict has the shape ``{"model": "...", "pk": ..., "fields": {...}}``.
        Call ``load()`` to also instantiate model objects.
        """
        raise NotImplementedError

    async def load(self, data: str) -> list:
        """
        Deserialize ``data`` and upsert each record into the database.

        Returns the list of saved model instances.
        """
        records = self.deserialize(data)
        return await _load_records(records)


async def _load_records(records: list[dict]) -> list:
    """
    Given a list of ``{"model": dotted_name, "pk": val, "fields": {…}}`` dicts,
    find or create each model instance and save it.

    Batches the existence check per model class (one SELECT per model, not one per record).
    """
    from collections import defaultdict

    from buraq.utils.module_loading import import_string

    # Group records by resolved model class, preserving order via index
    model_map: dict[str, type] = {}
    grouped: dict[type, list[dict]] = defaultdict(list)

    for rec in records:
        model_path = rec.get("model", "")
        if model_path not in model_map:
            try:
                model_map[model_path] = import_string(model_path)
            except (ImportError, AttributeError):
                model_map[model_path] = None  # type: ignore[assignment]
        model_cls = model_map[model_path]
        if model_cls is not None:
            grouped[model_cls].append(rec)

    saved = []
    for model_cls, recs in grouped.items():
        # Fetch all existing PKs for this model in one query
        pk_recs = [(rec["pk"], rec) for rec in recs if rec.get("pk") is not None]
        new_recs = [rec for rec in recs if rec.get("pk") is None]

        existing: dict = {}
        if pk_recs:
            pks = [pk for pk, _ in pk_recs]
            try:
                instances = await model_cls.objects.filter(id__in=pks).all()
                existing = {inst.id: inst for inst in instances}
            except Exception:
                pass

        for pk, rec in pk_recs:
            fields = rec.get("fields", {})
            if pk in existing:
                inst = existing[pk]
                for k, v in fields.items():
                    setattr(inst, k, v)
            else:
                inst = model_cls(**fields)
            await inst.save()
            saved.append(inst)

        for rec in new_recs:
            inst = model_cls(**rec.get("fields", {}))
            await inst.save()
            saved.append(inst)

    return saved
