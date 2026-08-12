# Serialization

`buraq.serializers` converts querysets and model instances to JSON, Python, XML, or YAML and back — including full round-trip loading back into the database.

## Serialize a queryset

```python
from buraq.serializers import serialize

posts = await Post.objects.filter(published=True).all()

json_str = await serialize("json", posts)
json_str = await serialize("json", posts, indent=2)  # pretty-print

xml_str  = await serialize("xml", posts)
py_str   = await serialize("python", posts)
yaml_str = await serialize("yaml", posts)   # requires: pip install pyyaml
```

## Deserialize — raw dicts

```python
from buraq.serializers import deserialize

records = deserialize("json", json_str)
# [{"model": "blog.Post", "pk": 1, "fields": {"title": "Hello", ...}}, ...]
```

## Round-trip — load into the database

`deserialize_objects()` deserializes and upserts each record into the database, returning saved model instances. Existing rows are looked up by PK; new rows are created if no match is found.

```python
from buraq.serializers import deserialize_objects

# From a fixture file
with open("fixtures/posts.json") as f:
    data = f.read()

posts = await deserialize_objects("json", data)
# → [<Post id=1>, <Post id=2>, ...]
```

Or call `load()` directly on a serializer instance:

```python
from buraq.serializers import get_serializer

serializer = get_serializer("yaml")
posts = await serializer.load(yaml_str)
```

## Formats

| Format | Serializer class | Notes |
|---|---|---|
| `"json"` | `JsonSerializer` (`buraq.serializers.json`) | Uses `orjson` when installed, stdlib `json` fallback |
| `"python"` | `PythonSerializer` (`buraq.serializers.python`) | `repr()` / `ast.literal_eval()` round-trip |
| `"xml"` | `XmlSerializer` (`buraq.serializers.xml`) | `xml.etree.ElementTree`, no extra dependencies |
| `"yaml"` | `YamlSerializer` (`buraq.serializers.yaml`) | PyYAML; `pip install pyyaml` required |

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

## BuraqJSONEncoder

`BuraqJSONEncoder` is a `json.JSONEncoder` subclass that handles extra Python types for use wherever a stdlib `cls=` encoder is needed:

| Type | Output |
|---|---|
| `datetime.datetime` / `datetime.time` | ISO 8601 string; microseconds omitted when zero |
| `datetime.date` | ISO 8601 string |
| `datetime.timedelta` | Total seconds as float |
| `decimal.Decimal` | String |
| `uuid.UUID` | String |
| Objects with `__json__()` | Return value of `__json__()` |

```python
import json
from buraq.utils.json import BuraqJSONEncoder

payload = json.dumps({"ts": datetime.now(), "id": uuid4()}, cls=BuraqJSONEncoder)
```

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
