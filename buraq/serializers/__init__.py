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


def get_serializer(format: str):
    try:
        return _REGISTRY[format]()
    except KeyError:
        raise SerializationError(f"Unknown serialization format: {format!r}. "
                                 f"Available: {list(_REGISTRY)}")


async def serialize(format: str, queryset, *, indent: int | None = None) -> str:
    return await get_serializer(format).serialize(queryset, indent=indent)


def deserialize(format: str, data: str):
    return get_serializer(format).deserialize(data)


__all__ = [
    "serialize", "deserialize", "get_serializer",
    "SerializationError", "DeserializationError",
]
