"""
YAML serializer for Buraq.

Requires PyYAML::

    pip install pyyaml

Usage::

    from buraq.serializers import serialize, deserialize

    yaml_str = await serialize("yaml", await Post.objects.all())
    objects  = deserialize("yaml", yaml_str)
"""
from __future__ import annotations

from buraq.serializers.base import DeserializationError, SerializationError
from buraq.serializers.json import JsonSerializer


class YamlSerializer(JsonSerializer):
    """Serializes to YAML using PyYAML."""

    def _check_yaml(self):
        try:
            import yaml
            return yaml
        except ImportError as err:
            raise SerializationError(
                "YAML serialization requires PyYAML. Install with: pip install pyyaml"
            ) from err

    async def serialize(self, queryset, *, indent: int | None = 2) -> str:
        yaml = self._check_yaml()
        from buraq.serializers.base import _to_record
        objects = queryset if isinstance(queryset, list) else list(queryset)
        records = [_to_record(obj) for obj in objects]
        return yaml.dump(records, allow_unicode=True, default_flow_style=False)

    def deserialize(self, data: str) -> list:
        yaml = self._check_yaml()
        try:
            return yaml.safe_load(data) or []
        except yaml.YAMLError as exc:
            raise DeserializationError(f"YAML deserialization error: {exc}") from exc
