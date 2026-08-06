from __future__ import annotations

from buraq.serializers.base import BaseSerializer, DeserializationError, _to_record


class PythonSerializer(BaseSerializer):
    async def serialize(self, queryset, *, indent=None) -> str:
        objects = queryset if isinstance(queryset, list) else list(queryset)
        return repr([_to_record(obj) for obj in objects])

    def deserialize(self, data: str):
        try:
            import ast
            return ast.literal_eval(data)
        except Exception as e:
            raise DeserializationError(str(e)) from e
