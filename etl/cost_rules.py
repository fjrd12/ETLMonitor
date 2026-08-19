"""(MESTYP, STATUS) -> estimated cost lookup (architecture.html §5)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CostRule:
    amount: float
    currency: str
    severity: str


class CostRules:
    def __init__(self, resources_root: Path):
        data = json.loads((resources_root / "cost_rules.json").read_text())
        self._rules = {(r["mestyp"], r["status"]): CostRule(r["amount"], r["currency"], r["severity"]) for r in data["rules"]}
        d = data["default"]
        self._default = CostRule(d["amount"], d["currency"], d["severity"])

    def lookup(self, mestyp: str, status: str) -> CostRule:
        return self._rules.get((mestyp, status), self._default)
