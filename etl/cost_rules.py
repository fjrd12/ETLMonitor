"""(MESTYP, STATUS) -> severity lookup.

Monetary/quantity value now comes from the real per-MESTYP XSLT valuation
(etl/monetizer.py); this table only classifies operational severity of the
underlying IDoc error status, which the XSLT valuation doesn't speak to.
"""
from __future__ import annotations

import json
from pathlib import Path


class CostRules:
    def __init__(self, resources_root: Path):
        data = json.loads((resources_root / "cost_rules.json").read_text())
        self._rules = {(r["mestyp"], r["status"]): r["severity"] for r in data["rules"]}
        self._default = data["default"]["severity"]

    def severity(self, mestyp: str, status: str) -> str:
        return self._rules.get((mestyp, status), self._default)
