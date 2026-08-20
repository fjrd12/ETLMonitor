"""Deterministic static HTML dashboard generator.

Reads every servers/<SERVER>/DW/idoc_events.db, renders a landing page
(sortable/filterable table + summary aggregates) and one
event_detail_<uuid>.html per event from DB state alone. Re-running against
unchanged DBs and resources produces byte-identical output — no wall-clock
content is baked in.
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from lxml import etree

from dashboard import charts
from etl.common import safe_uuid_dirname

TEMPLATES_DIR = Path(__file__).parent / "templates"

DASHBOARD_TITLE = "B2B Communication Analysis"

NAV_INDEX = [
    ("error-trend", "Error Trend"),
    ("by-system", "By system"),
    ("by-error-type", "By error type"),
    ("cost-by-server", "Cost by server"),
    ("events", "Events"),
]

NAV_DETAIL = [
    ("summary", "Summary"),
    ("valuation", "Valuation"),
    ("control-record", "Control record"),
    ("status", "Status"),
    ("messages", "Messages"),
    ("idoc-content", "IDoc content"),
]

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


def load_detail(db_path: str, event_uuid: str) -> tuple[list[dict], dict | None, dict, list[dict], dict | None]:
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
    last_message = max(messages, key=lambda m: (m["logdat"], m["logtim"], m["countr"]), default=None)
    return messages, control_record, status_table, valuations, last_message


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
    """One wide 'Error Trend' report merging event volume, per-MESTYP counts,
    and per-currency monetary totals (non-monetary valuation types — object
    counts, quantities, unvalued — are left out; the timeline chart above
    covers the same monetary ground with a legend). Columns are ordered by
    their total value across all months, highest first.
    """
    months = sorted({e["event_date"][:7] for e in events})
    mestyp_totals: dict[str, float] = defaultdict(float)
    currency_totals: dict[str, float] = defaultdict(float)
    for e in events:
        mestyp_totals[e["mestyp"]] += e["valuation_value"] or 0.0
        if e["valuation_type"] == "AMOUNT" and e["valuation_unit"]:
            currency_totals[e["valuation_unit"]] += e["valuation_value"] or 0.0

    mestyp_columns = sorted(mestyp_totals, key=lambda m: mestyp_totals[m], reverse=True)
    currency_columns = sorted(currency_totals, key=lambda c: currency_totals[c], reverse=True)

    def empty_bucket():
        return {
            "events": 0,
            "by_mestyp": defaultdict(int),
            "by_currency": defaultdict(float),
        }

    buckets: dict[str, dict] = defaultdict(empty_bucket)
    total_bucket = empty_bucket()
    for e in events:
        month = e["event_date"][:7]
        is_amount = e["valuation_type"] == "AMOUNT" and e["valuation_unit"]
        for b in (buckets[month], total_bucket):
            b["events"] += 1
            b["by_mestyp"][e["mestyp"]] += 1
            if is_amount:
                b["by_currency"][e["valuation_unit"]] += e["valuation_value"] or 0.0

    def row_for(month: str, b: dict) -> dict:
        return {
            "month": month,
            "events": fmt_int(b["events"]),
            "by_mestyp": [fmt_int(b["by_mestyp"].get(m, 0)) if b["by_mestyp"].get(m) else "—" for m in mestyp_columns],
            "by_currency": [fmt_num(b["by_currency"].get(c, 0.0)) if b["by_currency"].get(c) else "—" for c in currency_columns],
        }

    rows = [row_for(m, buckets[m]) for m in months]
    total_row = row_for("Total", total_bucket)

    return {
        "mestyp_columns": mestyp_columns,
        "currency_columns": currency_columns,
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
        lambda e: (e["server"], e["sndprn"], e["rcvprn"], e["currency"]),
        ("server", "sndprn", "rcvprn", "currency"),
        sort_key="total_amount",
    )

    error_type_totals: dict[tuple, dict] = defaultdict(
        lambda: {"event_count": 0, "total_amount": 0.0, "messages": Counter()}
    )
    for e in events:
        t = error_type_totals[(e["mestyp"], e["status"], e["currency"])]
        t["event_count"] += 1
        t["total_amount"] += e["amount"] or 0.0
        t["messages"][e["statxt"]] += 1
    agg_by_error_type = []
    for (mestyp, status, currency), t in error_type_totals.items():
        top_msg, _ = t["messages"].most_common(1)[0]
        distinct = len(t["messages"])
        message = top_msg if distinct == 1 else f"{top_msg} (+{distinct - 1} more)"
        agg_by_error_type.append(
            {
                "mestyp": mestyp,
                "status": status,
                "currency": currency,
                "event_count": t["event_count"],
                "total_amount": t["total_amount"],
                "event_count_fmt": fmt_int(t["event_count"]),
                "total_amount_fmt": fmt_num(t["total_amount"]),
                "message": message,
            }
        )
    agg_by_error_type.sort(key=lambda r: r["event_count"], reverse=True)

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

    all_months = sorted({e["event_date"][:7] for e in events})
    month_currency_amounts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    currencies_seen: set[str] = set()
    for e in events:
        if e["amount"] is not None:
            month_currency_amounts[e["event_date"][:7]][e["currency"]] += e["amount"]
            currencies_seen.add(e["currency"])
    chart_series = [
        (f"Total cost ({cur})", [month_currency_amounts[m].get(cur, 0.0) for m in all_months])
        for cur in sorted(currencies_seen)
    ]
    chart_month_amount = charts.multi_line_chart(all_months, chart_series)

    mestyp_counts = Counter(e["mestyp"] for e in events)
    chart_mestyp_pie = charts.pie_chart(sorted(mestyp_counts.items(), key=lambda kv: kv[1], reverse=True))

    chart_server_cost = charts.bar_chart_by_category(
        [(row["server"], row["total_amount"], row["currency"]) for row in agg_cost]
    )

    return {
        "agg_by_system": agg_by_system,
        "agg_by_error_type": agg_by_error_type,
        "agg_cost": agg_cost,
        "monthly": build_monthly_matrix(events),
        "chart_month_amount": chart_month_amount,
        "chart_mestyp_pie": chart_mestyp_pie,
        "chart_server_cost": chart_server_cost,
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
            title=DASHBOARD_TITLE,
            nav=NAV_INDEX,
            events=events,
            servers=servers,
            base_css=base_css,
            columns=EVENT_COLUMNS,
            **aggregate(events),
        )
    )

    detail_tpl = env.get_template("event_detail.html")
    for e in events:
        messages, control_record, status_table, valuations, last_message = load_detail(e["_db_path"], e["event_uuid"])
        content_path = find_content_xml(servers_root, e["server"], e["event_uuid"])
        raw_xml = pretty_xml(content_path) if content_path else ""
        (out_dir / e["detail_href"]).write_text(
            detail_tpl.render(
                title=DASHBOARD_TITLE,
                nav=NAV_DETAIL,
                event=e,
                messages=messages,
                last_message=last_message,
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
