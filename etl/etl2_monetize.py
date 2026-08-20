"""ETL 2 — monetize.

For each UUID folder under servers/<SERVER>/input, looks up MESTYP in
monetizer.json, resolves the matching .xslt, and runs it against CONTENT.xml
to produce a sidecar {DOCNUM}_VALUATION.xml (an <IDOC_VALUATION> document —
see resources/xslt/*.xslt). CONTENT.xml itself is left untouched: it's the
raw payload ETL 3 and the dashboard drill-down still read from. The full
quadruplet (CTRL, STAT, CONTENT, VALUATION) then moves to
servers/<SERVER>/output.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from lxml import etree

from etl.models import CtrlRecord
from etl.monetizer import Monetizer

logger = logging.getLogger(__name__)


def unsupported_valuation(docnum: int, mestyp: str, idoctp: str) -> bytes:
    """Matches the shape the XSLTs themselves emit on a MESTYP/IDOCTYP
    mismatch, for MESTYPs that have no valuation rule mapped at all.
    """
    root = etree.Element("IDOC_VALUATION")
    etree.SubElement(root, "DOCNUM").text = str(docnum)
    etree.SubElement(root, "MESTYP").text = mestyp
    etree.SubElement(root, "IDOCTYP").text = idoctp
    etree.SubElement(root, "STATUS").text = "UNSUPPORTED_MESTYP_OR_IDOCTYP"
    etree.SubElement(root, "EXPECTED").text = "no monetizer.json rule for this MESTYP"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def monetize_uuid_folder(uuid_dir: Path, output_root: Path, monetizer: Monetizer) -> Path:
    stem = next(p.name.removesuffix("_CTRL.json") for p in uuid_dir.glob("*_CTRL.json"))
    ctrl_path = uuid_dir / f"{stem}_CTRL.json"
    stat_path = uuid_dir / f"{stem}_STAT.json"
    content_path = uuid_dir / f"{stem}_CONTENT.xml"

    ctrl = CtrlRecord.model_validate(json.loads(ctrl_path.read_text()))
    control = ctrl.CONTROL

    if monetizer.has_rule(control.MESTYP):
        valuation_bytes = monetizer.transform(control.MESTYP, content_path.read_bytes())
    else:
        valuation_bytes = unsupported_valuation(control.DOCNUM, control.MESTYP, control.IDOCTP)

    valuation_path = uuid_dir / f"{stem}_VALUATION.xml"
    valuation_path.write_bytes(valuation_bytes)

    dest = output_root / uuid_dir.name
    dest.mkdir(parents=True, exist_ok=True)
    for src in (ctrl_path, stat_path, content_path, valuation_path):
        shutil.move(str(src), str(dest / src.name))
    uuid_dir.rmdir()

    logger.info("valuated %s (%s) -> %s", stem, control.MESTYP, dest)
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
    print(f"valuated {len(results)} event(s)")
