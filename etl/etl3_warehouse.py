"""ETL 3 — warehouse.

For each UUID folder under servers/<SERVER>/output, parses the valuated
quadruplet (CTRL, STAT, CONTENT, VALUATION), classifies severity, and
upserts an ErrorEvent (+ its Messages, Event_Meta segments, and
Event_Valuations) into the configured EventSink.
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
from etl.models import MetaField, StatRecord, Valuation
from etl.sinks import EventSink, SqliteEventSink

logger = logging.getLogger(__name__)

# Valuation statuses where VALUE/UNIT reflect a real computed number, as
# opposed to a rule mismatch or missing source data in the payload.
COMPUTED_STATUSES = {"VALUATED", "VALUATED_WITH_OPERATIONAL_FALLBACK"}


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


def extract_valuations(valuation_path: Path) -> tuple[list[Valuation], str]:
    """Parse an <IDOC_VALUATION> sidecar (see resources/xslt/*.xslt) into
    Valuation DTOs, plus the document's top-level <STATUS> (only present
    when there's no <VALUATIONS> child, i.e. a MESTYP/IDOCTYP mismatch or a
    missing monetizer.json rule).
    """
    root = etree.parse(str(valuation_path)).getroot()
    valuations = [
        Valuation(
            type=(v.findtext("TYPE") or "").strip(),
            value=float(v.findtext("VALUE") or 0),
            unit=(v.findtext("UNIT") or "").strip(),
            source=(v.findtext("SOURCE") or "").strip(),
            status=(v.findtext("STATUS") or "").strip(),
            primary=(v.get("primary") == "true"),
        )
        for v in root.findall("./VALUATIONS/VALUATION")
    ]
    top_status = (root.findtext("STATUS") or "").strip()
    return valuations, top_status


def primary_valuation(valuations: list[Valuation], fallback_status: str) -> Valuation:
    for v in valuations:
        if v.primary:
            return v
    if valuations:
        return valuations[0]
    return Valuation(type="NONE", value=0.0, unit="", source="", status=fallback_status, primary=False)


def load_event(
    uuid_dir: Path, cost_rules: CostRules
) -> tuple[ErrorEvent, list[MessageDTO], list[EventMetaDTO], list[Valuation]]:
    stem = next(p.name.removesuffix("_CTRL.json") for p in uuid_dir.glob("*_CTRL.json"))
    ctrl_path = uuid_dir / f"{stem}_CTRL.json"
    stat_path = uuid_dir / f"{stem}_STAT.json"
    content_path = uuid_dir / f"{stem}_CONTENT.xml"
    valuation_path = uuid_dir / f"{stem}_VALUATION.xml"

    ctrl = CtrlRecord.model_validate(json.loads(ctrl_path.read_text()))
    stat = StatRecord.model_validate(json.loads(stat_path.read_text()))
    control = ctrl.CONTROL

    valuations, top_status = extract_valuations(valuation_path)
    primary = primary_valuation(valuations, top_status or "UNSUPPORTED_MESTYP_OR_IDOCTYP")

    is_amount = primary.type == "AMOUNT" and primary.status in COMPUTED_STATUSES

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
        amount=primary.value if is_amount else None,
        currency=primary.unit if is_amount else None,
        severity=cost_rules.severity(control.MESTYP, control.STATUS),
        monetized=True,
        valuation_type=primary.type,
        valuation_value=primary.value if primary.type != "NONE" else None,
        valuation_unit=primary.unit or None,
        valuation_status=primary.status,
        valuation_source=primary.source or None,
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
    return event, messages, meta, valuations


def run(servers_root: Path, resources_root: Path) -> int:
    cost_rules = CostRules(resources_root)
    count = 0
    for server_dir in sorted(p for p in servers_root.iterdir() if p.is_dir()):
        output_root = server_dir / "output"
        if not output_root.exists():
            continue
        sink: EventSink = SqliteEventSink(server_dir / "DW" / "idoc_events.db")
        for uuid_dir in sorted(p for p in output_root.iterdir() if p.is_dir()):
            event, messages, meta, valuations = load_event(uuid_dir, cost_rules)
            sink.upsert_event(event)
            sink.upsert_messages(event.event_uuid, messages)
            sink.upsert_meta(event.event_uuid, meta)
            sink.upsert_valuations(event.event_uuid, valuations)
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
