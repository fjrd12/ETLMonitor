"""ETL 2 — monetize.

For each UUID folder under servers/<SERVER>/input, looks up MESTYP in
monetizer.json, resolves the matching .xslt, transforms CONTENT.xml, and
moves the triplet (CTRL, STAT, monetized CONTENT) to servers/<SERVER>/output.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from etl.models import CtrlRecord
from etl.monetizer import Monetizer

logger = logging.getLogger(__name__)


def monetize_uuid_folder(uuid_dir: Path, output_root: Path, monetizer: Monetizer) -> Path:
    stem = next(p.name.removesuffix("_CTRL.json") for p in uuid_dir.glob("*_CTRL.json"))
    ctrl_path = uuid_dir / f"{stem}_CTRL.json"
    stat_path = uuid_dir / f"{stem}_STAT.json"
    content_path = uuid_dir / f"{stem}_CONTENT.xml"

    ctrl = CtrlRecord.model_validate(json.loads(ctrl_path.read_text()))
    monetized_xml = monetizer.transform(ctrl.CONTROL.MESTYP, content_path.read_bytes())
    content_path.write_bytes(monetized_xml)

    dest = output_root / uuid_dir.name
    dest.mkdir(parents=True, exist_ok=True)
    for src in (ctrl_path, stat_path, content_path):
        shutil.move(str(src), str(dest / src.name))
    uuid_dir.rmdir()

    logger.info("monetized %s (%s) -> %s", stem, ctrl.CONTROL.MESTYP, dest)
    return dest


def run(servers_root: Path, resources_root: Path) -> list[Path]:
    monetizer = Monetizer(resources_root)
    monetized: list[Path] = []
    for server_dir in sorted(p for p in servers_root.iterdir() if p.is_dir()):
        input_root = server_dir / "input"
        output_root = server_dir / "output"
        if not input_root.exists():
            continue
        for uuid_dir in sorted(p for p in input_root.iterdir() if p.is_dir()):
            monetized.append(monetize_uuid_folder(uuid_dir, output_root, monetizer))
    return monetized


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--servers-root", type=Path, default=Path("servers"))
    parser.add_argument("--resources-root", type=Path, default=Path("resources"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    results = run(args.servers_root, args.resources_root)
    print(f"monetized {len(results)} event(s)")
