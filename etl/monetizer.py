"""Strategy-pattern dispatch: MESTYP -> XSLT transform (architecture.html §3)."""
from __future__ import annotations

import json
from pathlib import Path

from lxml import etree


class Monetizer:
    def __init__(self, resources_root: Path):
        self._resources_root = resources_root
        table = json.loads((resources_root / "monetizer.json").read_text())
        self._dispatch = {mestyp: resources_root / rel for mestyp, rel in table.items()}
        self._transform_cache: dict[Path, etree.XSLT] = {}

    def _transform_for(self, xslt_path: Path) -> etree.XSLT:
        if xslt_path not in self._transform_cache:
            self._transform_cache[xslt_path] = etree.XSLT(etree.parse(str(xslt_path)))
        return self._transform_cache[xslt_path]

    def transform(self, mestyp: str, xml_bytes: bytes) -> bytes:
        xslt_path = self._dispatch.get(mestyp)
        if xslt_path is None:
            raise KeyError(f"no monetizer.json entry for MESTYP={mestyp!r}")
        transform = self._transform_for(xslt_path)
        source = etree.fromstring(xml_bytes)
        result = transform(source)
        return etree.tostring(result, xml_declaration=True, encoding="UTF-8")

    def has_rule(self, mestyp: str) -> bool:
        return mestyp in self._dispatch
