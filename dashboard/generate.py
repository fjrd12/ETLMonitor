"""Deterministic static HTML dashboard generator.

Reads every servers/<SERVER>/DW/idoc_events.db, renders a landing page
(sortable/filterable table + summary aggregates) and one
event_detail_<uuid>.html per event from DB state alone. Re-running against
unchanged DBs and resources produces byte-identical output — no wall-clock
content is baked in.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from lxml import etree

from etl.common import safe_uuid_dirname

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Status -> badge CSS class (reuses the severity badge palette in base.css).
VALUATION_BADGE = {
    "VALUATED": "low",
    "VALUATED_WITH_OPERATIONAL_FALLBACK": "medium",
    "UNAVAILABLE": "high",
    "UNSUPPORTED_MESTYP_OR_IDOCTYP": "unknown",
}

# The columns of the main events table, in display order. Used both to
# render <th>s and to drive the show/hide-column filter control.
EVENT_COLUMNS = [
    ("event_date", "Date", "text"),
    ("server", "Server", "text"),
    ("mestyp", "MESTYP", "text"),
    ("status", "Status", "text"),
    ("docnum", "DocNum", "num"),
    ("valuation_display", "Business value", "num"),
]


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def fmt_num(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def fmt_int(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def load_all_events(servers_root: Path) -> list[dict]:
    events: list[dict] = []
    for db_path in sorted(servers_root.glob("*/DW/idoc_events.db")):
        with sqlite3.connect(db_path) as conn:
            for e in _rows(conn, "SELECT * FROM ErrorEvents"):
                e["_db_path"] = str(db_path)
                events.append(e)
    events.sort(key=lambda e: e["docnum"])
    return events


def load_detail(db_path: str, event_uuid: str) -> tuple[list[dict], dict | None, dict, list[dict]]:
    with sqlite3.connect(db_path) as conn:
        messages = _rows(
            conn,
            "SELECT * FROM Messages WHERE event_uuid = ? ORDER BY countr",
            (event_uuid,),
        )
        meta_rows = _rows(
            conn,
            "SELECT * FROM Event_Meta WHERE event_uuid = ? ORDER BY id",
            (event_uuid,),
        )
        meta = []
        for m in meta_rows:
            fields = _rows(
                conn,
                "SELECT * FROM Event_meta_field WHERE meta_id = ? ORDER BY id",
                (m["id"],),
            )
            meta.append({"segment": m["segment"], "fields": fields})
        valuations = _rows(
            conn,
            "SELECT * FROM Event_Valuations WHERE event_uuid = ? ORDER BY is_primary DESC, id",
            (event_uuid,),
        )
        for v in valuations:
            v["badge"] = VALUATION_BADGE.get(v["status"], "unknown")
            v["value_fmt"] = fmt_num(v["value"], 3).rstrip("0").rstrip(".")

    control_record = next((m for m in meta if m["segment"] == "EDI_DC40"), None)
    status_records = [m for m in meta if m["segment"] == "EDI_DS40"]
    status_table = tabulate_records(status_records)
    return messages, control_record, status_table, valuations


def tabulate_records(records: list[dict]) -> dict:
    """Transpose a list of same-shaped {"fields": [{field_name, field_value}]}
    meta records into a {headers, rows} table for rendering.
    """
    if not records:
        return {"headers": [], "rows": []}
    headers = [f["field_name"] for f in records[0]["fields"]]
    rows = [[f["field_value"] for f in r["fields"]] for r in records]
    return {"headers": headers, "rows": rows}


def find_content_xml(servers_root: Path, server: str, event_uuid: str) -> Path | None:
    uuid_dir = servers_root / server / "output" / safe_uuid_dirname(event_uuid)
    matches = list(uuid_dir.glob("*_CONTENT.xml"))
    return matches[0] if matches else None


def pretty_xml(content_path: Path) -> str:
    tree = etree.parse(str(content_path))
    etree.indent(tree, space="  ")
    return etree.tostring(tree, pretty_print=True, encoding="unicode")


def format_valuation(value: float | None, unit: str | None, vtype: str) -> str:
    if vtype in (None, "NONE") or value is None:
        return "—"
    if vtype == "AMOUNT":
        return f"{fmt_num(value)} {unit}".strip()
    return f"{fmt_num(value, 3).rstrip('0').rstrip('.')} {unit}".strip()


def annotate_valuation(e: dict) -> None:
    e["valuation_display"] = format_valuation(e["valuation_value"], e["valuation_unit"], e["valuation_type"])
    e["valuation_badge"] = VALUATION_BADGE.get(e["valuation_status"], "unknown")
    e["amount_fmt"] = fmt_num(e["amount"]) if e["amount"] is not None else None


def build_monthly_matrix(events: list[dict]) -> dict:
    """One wide 'by month' report merging event volume, per-MESTYP counts,
    and per-(valuation_type,unit) totals. Columns are ordered by their total
    value across all months, highest first.
    """
    months = sorted({e["event_date"][:7] for e in events})
    mestyp_totals: dict[str, float] = defaultdict(float)
    unit_totals: dict[tuple[str, str], float] = defaultdict(float)
    for e in events:
        mestyp_totals[e["mestyp"]] += e["valuation_value"] or 0.0
        unit_totals[(e["valuation_type"], e["valuation_unit"] or "")] += e["valuation_value"] or 0.0

    mestyp_columns = sorted(mestyp_totals, key=lambda m: mestyp_totals[m], reverse=True)
    unit_columns = sorted(unit_totals, key=lambda k: unit_totals[k], reverse=True)

    def empty_bucket():
        return {
            "events": 0,
            "by_mestyp": defaultdict(int),
            "by_unit": defaultdict(float),
        }

    buckets: dict[str, dict] = defaultdict(empty_bucket)
    total_bucket = empty_bucket()
    for e in events:
        month = e["event_date"][:7]
        b = buckets[month]
        b["events"] += 1
        b["by_mestyp"][e["mestyp"]] += 1
        b["by_unit"][(e["valuation_type"], e["valuation_unit"] or "")] += e["valuation_value"] or 0.0
        total_bucket["events"] += 1
        total_bucket["by_mestyp"][e["mestyp"]] += 1
        total_bucket["by_unit"][(e["valuation_type"], e["valuation_unit"] or "")] += e["valuation_value"] or 0.0

    def row_for(month: str, b: dict) -> dict:
        return {
            "month": month,
            "events": fmt_int(b["events"]),
            "by_mestyp": [fmt_int(b["by_mestyp"].get(m, 0)) if b["by_mestyp"].get(m) else "—" for m in mestyp_columns],
            "by_unit": [fmt_num(b["by_unit"].get(u, 0.0)) if b["by_unit"].get(u) else "—" for u in unit_columns],
        }

    rows = [row_for(m, buckets[m]) for m in months]
    total_row = row_for("Total", total_bucket)

    return {
        "mestyp_columns": mestyp_columns,
        "unit_columns": [f"{unit} ({vtype})" if unit else vtype for vtype, unit in unit_columns],
        "rows": rows,
        "total_row": total_row,
    }


def aggregate(events: list[dict]) -> dict[str, list[dict]]:
    def group_sum(key_fn, keys: tuple[str, ...], sort_key="event_count"):
        totals: dict[tuple, dict] = defaultdict(lambda: {"event_count": 0, "total_amount": 0.0})
        for e in events:
            k = key_fn(e)
            totals[k]["event_count"] += 1
            totals[k]["total_amount"] += e["amount"] or 0.0
        out = []
        for k, v in totals.items():
            row = dict(zip(keys, k))
            row.update(v)
            out.append(row)
        out.sort(key=lambda r: r[sort_key], reverse=True)
        for row in out:
            row["event_count_fmt"] = fmt_int(row["event_count"])
            row["total_amount_fmt"] = fmt_num(row["total_amount"])
        return out

    agg_by_system = group_sum(
        lambda e: (e["server"], e["sndprn"], e["rcvprn"]), ("server", "sndprn", "rcvprn"), sort_key="total_amount"
    )
    agg_by_error_type = group_sum(lambda e: (e["mestyp"], e["status"]), ("mestyp", "status"), sort_key="event_count")

    cost_totals: dict[tuple, dict] = defaultdict(lambda: {"event_count": 0, "total_amount": 0.0})
    for e in events:
        if e["amount"] is None:
            continue
        k = (e["server"], e["currency"])
        cost_totals[k]["event_count"] += 1
        cost_totals[k]["total_amount"] += e["amount"]
    agg_cost = [{"server": k[0], "currency": k[1], **v} for k, v in cost_totals.items()]
    agg_cost.sort(key=lambda r: r["total_amount"], reverse=True)
    for row in agg_cost:
        row["event_count_fmt"] = fmt_int(row["event_count"])
        row["total_amount_fmt"] = fmt_num(row["total_amount"])

    return {
        "agg_by_system": agg_by_system,
        "agg_by_error_type": agg_by_error_type,
        "agg_cost": agg_cost,
        "monthly": build_monthly_matrix(events),
    }


def generate(servers_root: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    base_css = (TEMPLATES_DIR / "base.css").read_text()
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

    events = load_all_events(servers_root)
    servers = sorted({e["server"] for e in events})

    for e in events:
        e["detail_href"] = f"event_detail_{safe_uuid_dirname(e['event_uuid'])}.html"
        annotate_valuation(e)

    index_tpl = env.get_template("index.html")
    (out_dir / "index.html").write_text(
        index_tpl.render(
            events=events,
            servers=servers,
            base_css=base_css,
            columns=EVENT_COLUMNS,
            **aggregate(events),
        )
    )

    detail_tpl = env.get_template("event_detail.html")
    for e in events:
        messages, control_record, status_table, valuations = load_detail(e["_db_path"], e["event_uuid"])
        content_path = find_content_xml(servers_root, e["server"], e["event_uuid"])
        raw_xml = pretty_xml(content_path) if content_path else ""
        (out_dir / e["detail_href"]).write_text(
            detail_tpl.render(
                event=e,
                messages=messages,
                control_record=control_record,
                status_table=status_table,
                valuations=valuations,
                raw_xml=raw_xml,
                base_css=base_css,
            )
        )

    return len(events)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--servers-root", type=Path, default=Path("servers"))
    parser.add_argument("--out-dir", type=Path, default=Path("dashboard/out"))
    args = parser.parse_args()

    n = generate(args.servers_root, args.out_dir)
    print(f"generated dashboard for {n} event(s) -> {args.out_dir}")
