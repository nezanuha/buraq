"""
Serialization framework — convert querysets and model instances to JSON, Python dicts, or XML.

Usage:
    from buraq.serializers import serialize, deserialize

    data = await serialize("json", await Post.objects.all())
    data = await serialize("json", await Post.objects.filter(published=True), indent=2)
    data = await serialize("python", objs)
    data = await serialize("xml", objs)

    objects = deserialize("json", json_string)
"""
from __future__ import annotations

from buraq.serializers.base import DeserializationError, SerializationError
from buraq.serializers.json import JsonSerializer
from buraq.serializers.python import PythonSerializer
from buraq.serializers.xml import XmlSerializer

_REGISTRY: dict[str, type] = {
    "json": JsonSerializer,
    "python": PythonSerializer,
    "xml": XmlSerializer,
}

try:
    from buraq.serializers.yaml import YamlSerializer
    _REGISTRY["yaml"] = YamlSerializer
except Exception:
    pass


def get_serializer(format: str):
    try:
        return _REGISTRY[format]()
    except KeyError as err:
        raise SerializationError(
            f"Unknown serialization format: {format!r}. "
            f"Available: {list(_REGISTRY)}"
        ) from err


def register_serializer(format: str, serializer_class) -> None:
    """Register a custom serializer class under the given format name."""
    _REGISTRY[format] = serializer_class


async def serialize(format: str, queryset, *, indent: int | None = None) -> str:
    return await get_serializer(format).serialize(queryset, indent=indent)


def deserialize(format: str, data: str):
    return get_serializer(format).deserialize(data)


async def deserialize_objects(format: str, data: str) -> list:
    """
    Deserialize and return a list of model instances ready to save.

    Unlike ``deserialize()``, which returns raw dicts, this function
    reconstructs model instances from the serialized data.
    """
    raw = deserialize(format, data)
    if not raw:
        return []
    instances = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        model_label = item.get("model", "")
        fields = item.get("fields", item)
        pk = item.get("pk")
        if pk:
            fields = {**fields, "id": pk}
        if model_label:
            try:
                from buraq.utils.module_loading import import_string
                parts = model_label.rsplit(".", 1)
                if len(parts) == 2:
                    model_cls = import_string(f"{parts[0]}.models.{parts[1].title()}")
                else:
                    model_cls = import_string(model_label)
                instance = model_cls(**{k: v for k, v in fields.items() if k != "model"})
                instances.append(instance)
            except Exception:
                pass
        else:
            instances.append(fields)
    return instances


__all__ = [
    "serialize", "deserialize", "deserialize_objects",
    "get_serializer", "register_serializer",
    "SerializationError", "DeserializationError",
]
