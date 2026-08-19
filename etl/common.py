"""Shared helpers used across ETL stages."""
from __future__ import annotations

import base64
from pathlib import Path


def safe_uuid_dirname(global_uuid: str) -> str:
    """GLOBAL_UUID is base64 and can contain '/', which is unsafe as a path
    segment. Re-encode standard base64 as filesystem-safe base64 (RFC 4648 §5)
    so the folder name stays a lossless, reversible encoding of the UUID.
    """
    raw = base64.b64decode(global_uuid)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def find_triplets(landing_zone: Path) -> list[str]:
    """Return DOCNUM stems for every complete {DOCNUM}_CTRL/STAT/CONTENT triplet
    found directly under landing_zone, sorted for deterministic processing order.
    """
    docnums = set()
    for ctrl_file in landing_zone.glob("*_CTRL.json"):
        stem = ctrl_file.name.removesuffix("_CTRL.json")
        if (landing_zone / f"{stem}_STAT.json").exists() and (landing_zone / f"{stem}_CONTENT.xml").exists():
            docnums.add(stem)
    return sorted(docnums)


def triplet_paths(folder: Path, stem: str) -> tuple[Path, Path, Path]:
    return (
        folder / f"{stem}_CTRL.json",
        folder / f"{stem}_STAT.json",
        folder / f"{stem}_CONTENT.xml",
    )
