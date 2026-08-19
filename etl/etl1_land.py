"""ETL 1 — route & land.

Reads SNDPRN/RCVPRN from CTRL.CONTROL to determine the owning server, creates
servers/<SERVER>/{input,output,DW} if missing, creates
servers/<SERVER>/input/<GLOBAL_UUID>/ if missing, moves the CTRL/STAT/CONTENT
triplet there, and deletes it from the landing zone.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from pydantic import ValidationError

from etl.common import find_triplets, safe_uuid_dirname, triplet_paths
from etl.models import CtrlRecord, StatRecord

logger = logging.getLogger(__name__)


def server_for(ctrl: CtrlRecord) -> str:
    """The sending logical system is the source-of-truth server for a triplet:
    it identifies which SAP backend produced the error, independent of how
    many downstream receivers (RCVPRN) it fans out to.
    """
    return ctrl.CONTROL.SNDPRN


def land_triplet(landing_zone: Path, servers_root: Path, stem: str) -> Path:
    ctrl_path, stat_path, content_path = triplet_paths(landing_zone, stem)

    ctrl = CtrlRecord.model_validate(json.loads(ctrl_path.read_text()))
    StatRecord.model_validate(json.loads(stat_path.read_text()))  # fail loud on malformed STAT too

    server = server_for(ctrl)
    uuid_dir = safe_uuid_dirname(ctrl.GLOBAL_UUID)

    dest = servers_root / server / "input" / uuid_dir
    for sub in ("input", "output", "DW"):
        (servers_root / server / sub).mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)

    for src in (ctrl_path, stat_path, content_path):
        shutil.move(str(src), str(dest / src.name))

    logger.info("landed %s -> %s", stem, dest)
    return dest


def run(landing_zone: Path, servers_root: Path) -> list[Path]:
    landed: list[Path] = []
    for stem in find_triplets(landing_zone):
        try:
            landed.append(land_triplet(landing_zone, servers_root, stem))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError(f"malformed landing-zone record for {stem}: {exc}") from exc
    return landed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--landing-zone", type=Path, default=Path("input"))
    parser.add_argument("--servers-root", type=Path, default=Path("servers"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    results = run(args.landing_zone, args.servers_root)
    print(f"landed {len(results)} triplet(s)")
