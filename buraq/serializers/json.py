from __future__ import annotations

from buraq.serializers.base import BaseSerializer, DeserializationError, _to_record

try:
    import orjson

    def _dumps(obj, indent=None) -> str:
        opts = orjson.OPT_NON_STR_KEYS
        if indent:
            opts |= orjson.OPT_INDENT_2
        return orjson.dumps(obj, option=opts).decode()

    def _loads(s: str):
        return orjson.loads(s)

except ImportError:
    import json

    def _dumps(obj, indent=None) -> str:
        return json.dumps(obj, indent=indent, default=str)

    def _loads(s: str):
        return json.loads(s)


class JsonSerializer(BaseSerializer):
    async def serialize(self, queryset, *, indent=None) -> str:
        objects = queryset if isinstance(queryset, list) else list(queryset)
        return _dumps([_to_record(obj) for obj in objects], indent=indent)

    def deserialize(self, data: str):
        try:
            return _loads(data)
        except Exception as e:
            raise DeserializationError(str(e)) from e
