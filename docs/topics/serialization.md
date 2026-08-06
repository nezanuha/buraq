# Serialization

`buraq.serializers` converts querysets and model instances to JSON, Python, or XML and back.

## Serialize a queryset

```python
from buraq.serializers import serialize

posts = await Post.objects.filter(published=True).all()

json_str = await serialize("json", posts)
json_str = await serialize("json", posts, indent=2)  # pretty-print

xml_str  = await serialize("xml", posts)
py_str   = await serialize("python", posts)
```

## Deserialize

```python
from buraq.serializers import deserialize

records = deserialize("json", json_str)
# [{"model": "blog.Post", "pk": 1, "fields": {"title": "Hello", ...}}, ...]
```

## Formats

| Format | Module | Notes |
|---|---|---|
| `"json"` | `buraq.serializers.json` | Uses `orjson` (Rust-based) when installed, stdlib `json` fallback |
| `"python"` | `buraq.serializers.python` | `repr()` / `ast.literal_eval()` round-trip |
| `"xml"` | `buraq.serializers.xml` | `xml.etree.ElementTree`, no extra dependencies |

## Output format

Each serialized object is a dict with three keys:

```json
{
  "model": "blog.post",
  "pk": 1,
  "fields": {
    "title": "Hello World",
    "published": true,
    "created_at": "2026-08-06T12:00:00+00:00"
  }
}
```

`datetime`, `date`, `time`, and `Decimal` values are automatically converted to strings.

## Custom serializer

```python
from buraq.serializers import _REGISTRY
from buraq.serializers.base import BaseSerializer

class MsgpackSerializer(BaseSerializer):
    async def serialize(self, queryset, *, indent=None) -> str:
        import msgpack
        objects = list(queryset)
        return msgpack.dumps([_to_record(o) for o in objects])

    def deserialize(self, data: str):
        import msgpack
        return msgpack.loads(data)

_REGISTRY["msgpack"] = MsgpackSerializer
```
