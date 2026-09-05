"""Render API responses as XML."""

from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from rest_framework.renderers import BaseRenderer


def _build(parent: Element, data: Any) -> None:
    """Turn nested dicts, lists and scalars into child elements."""
    if isinstance(data, dict):
        for key, value in data.items():
            _build(SubElement(parent, str(key)), value)
    elif isinstance(data, (list, tuple)):
        for item in data:
            _build(SubElement(parent, "item"), item)
    elif data is None:
        parent.set("nil", "true")
    else:
        parent.text = str(data)


class XMLRenderer(BaseRenderer):
    """Serialise a response body as XML. Generates only - never parses."""

    media_type = "application/xml"
    format = "xml"
    charset = "utf-8"

    def render(self, data: Any, accepted_media_type=None, renderer_context=None) -> bytes:
        root = Element("response")
        _build(root, data)
        return tostring(root, encoding="utf-8", xml_declaration=True)
