"""ETL 3 — warehouse.

For each UUID folder under servers/<SERVER>/output, parses the monetized
triplet, looks up an estimated cost, and upserts an ErrorEvent (+ its
Messages and Event_Meta segments) into the configured EventSink.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from lxml import etree

from etl.cost_rules import CostRules
from etl.models import CtrlRecord, ErrorEvent
from etl.models import EventMeta as EventMetaDTO
from etl.models import Message as MessageDTO
from etl.models import MetaField, StatRecord
from etl.sinks import EventSink, SqliteEventSink

logger = logging.getLogger(__name__)


def extract_meta(content_path: Path) -> list[EventMetaDTO]:
    """Flatten each IDoc segment (direct child of <IDOC>) into an EventMeta
    with one MetaField per leaf element, so the dashboard can render the raw
    payload without re-parsing XML at request time.
    """
    root = etree.parse(str(content_path)).getroot()
    idoc = root.find(".//IDOC")
    if idoc is None:
        return []

    def leaves(el: etree._Element, prefix: str) -> list[MetaField]:
        children = list(el)
        if not children:
            text = (el.text or "").strip()
            return [MetaField(prefix, text)] if text else []
        out: list[MetaField] = []
        for child in children:
            out.extend(leaves(child, f"{prefix}.{child.tag}" if prefix else child.tag))
        return out

    return [EventMetaDTO(segment=segment.tag, fields=leaves(segment, "")) for segment in idoc]


def load_event(uuid_dir: Path, cost_rules: CostRules) -> tuple[ErrorEvent, list[MessageDTO], list[EventMetaDTO]]:
    stem = next(p.name.removesuffix("_CTRL.json") for p in uuid_dir.glob("*_CTRL.json"))
    ctrl_path = uuid_dir / f"{stem}_CTRL.json"
    stat_path = uuid_dir / f"{stem}_STAT.json"
    content_path = uuid_dir / f"{stem}_CONTENT.xml"

    ctrl = CtrlRecord.model_validate(json.loads(ctrl_path.read_text()))
    stat = StatRecord.model_validate(json.loads(stat_path.read_text()))
    control = ctrl.CONTROL

    cost = cost_rules.lookup(control.MESTYP, control.STATUS)

    event = ErrorEvent(
        event_uuid=ctrl.GLOBAL_UUID,
        docnum=control.DOCNUM,
        server=control.SNDPRN,
        sndprn=control.SNDPRN,
        rcvprn=control.RCVPRN,
        mestyp=control.MESTYP,
        idoctp=control.IDOCTP,
        status=control.STATUS,
        event_date=dt.date.fromisoformat(control.CREDAT),
        event_time=control.CRETIM,
        uname=stat.UNAME,
        statxt=stat.STATXT,
        loaded_at=dt.datetime.now(dt.timezone.utc),
        amount=cost.amount,
        currency=cost.currency,
        severity=cost.severity,
        monetized=True,
    )
    messages = [
        MessageDTO(
            countr=stat.COUNTR,
            status=stat.STATUS,
            statyp=stat.STATYP,
            statxt=stat.STATXT,
            uname=stat.UNAME,
            logdat=dt.date.fromisoformat(stat.LOGDAT),
            logtim=stat.LOGTIM,
        )
    ]
    meta = extract_meta(content_path)
    return event, messages, meta


def run(servers_root: Path, resources_root: Path) -> int:
    cost_rules = CostRules(resources_root)
    count = 0
    for server_dir in sorted(p for p in servers_root.iterdir() if p.is_dir()):
        output_root = server_dir / "output"
        if not output_root.exists():
            continue
        sink: EventSink = SqliteEventSink(server_dir / "DW" / "idoc_events.db")
        for uuid_dir in sorted(p for p in output_root.iterdir() if p.is_dir()):
            event, messages, meta = load_event(uuid_dir, cost_rules)
            sink.upsert_event(event)
            sink.upsert_messages(event.event_uuid, messages)
            sink.upsert_meta(event.event_uuid, meta)
            count += 1
            logger.info("warehoused %s (%s)", event.docnum, event.mestyp)
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--servers-root", type=Path, default=Path("servers"))
    parser.add_argument("--resources-root", type=Path, default=Path("resources"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    n = run(args.servers_root, args.resources_root)
    print(f"warehoused {n} event(s)")
