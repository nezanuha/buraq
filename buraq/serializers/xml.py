from __future__ import annotations

import xml.etree.ElementTree as ET

from buraq.serializers.base import BaseSerializer, DeserializationError, _to_record


class XmlSerializer(BaseSerializer):
    async def serialize(self, queryset, *, indent=None) -> str:
        objects = queryset if isinstance(queryset, list) else list(queryset)
        root = ET.Element("buraq-objects", version="1.0")
        for obj in objects:
            rec = _to_record(obj)
            obj_el = ET.SubElement(root, "object", model=rec["model"], pk=str(rec["pk"] or ""))
            for name, value in rec["fields"].items():
                field_el = ET.SubElement(obj_el, "field", name=name)
                field_el.text = "" if value is None else str(value)
        if indent:
            ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode")

    def deserialize(self, data: str):
        try:
            root = ET.fromstring(data)
            return [
                {
                    "model": obj_el.get("model"),
                    "pk": obj_el.get("pk"),
                    "fields": {f.get("name"): f.text for f in obj_el.findall("field")},
                }
                for obj_el in root.findall("object")
            ]
        except ET.ParseError as e:
            raise DeserializationError(str(e)) from e
