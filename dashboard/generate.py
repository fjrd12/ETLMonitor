"""Deterministic static HTML dashboard generator.

Reads every servers/<SERVER>/DW/idoc_events.db, renders a landing page
(sortable table + summary aggregates) and one event_detail_<uuid>.html per
event from DB state alone. Re-running against unchanged DBs and resources
produces byte-identical output — no wall-clock content is baked in.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from etl.common import safe_uuid_dirname

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def load_all_events(servers_root: Path) -> list[dict]:
    events: list[dict] = []
    for db_path in sorted(servers_root.glob("*/DW/idoc_events.db")):
        with sqlite3.connect(db_path) as conn:
            for e in _rows(conn, "SELECT * FROM ErrorEvents"):
                e["_db_path"] = str(db_path)
                events.append(e)
    events.sort(key=lambda e: e["docnum"])
    return events


def load_detail(db_path: str, event_uuid: str) -> tuple[list[dict], list[dict]]:
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
    return messages, meta


def find_content_xml(servers_root: Path, server: str, event_uuid: str) -> Path | None:
    uuid_dir = servers_root / server / "output" / safe_uuid_dirname(event_uuid)
    matches = list(uuid_dir.glob("*_CONTENT.xml"))
    return matches[0] if matches else None


def aggregate(events: list[dict]) -> dict[str, list[dict]]:
    def group_sum(key_fn, keys: tuple[str, ...]):
        totals: dict[tuple, dict] = defaultdict(lambda: {"event_count": 0, "total_amount": 0.0})
        for e in events:
            k = key_fn(e)
            totals[k]["event_count"] += 1
            totals[k]["total_amount"] += e["amount"] or 0.0
        out = []
        for k in sorted(totals):
            row = dict(zip(keys, k))
            row.update(totals[k])
            out.append(row)
        return out

    agg_monthly = group_sum(lambda e: (e["event_date"][:7],), ("month",))
    agg_by_system = group_sum(lambda e: (e["server"], e["sndprn"], e["rcvprn"]), ("server", "sndprn", "rcvprn"))
    agg_by_error_type = group_sum(lambda e: (e["mestyp"], e["status"]), ("mestyp", "status"))

    cost_totals: dict[tuple, dict] = defaultdict(lambda: {"event_count": 0, "total_amount": 0.0})
    for e in events:
        if e["amount"] is None:
            continue
        k = (e["server"], e["currency"])
        cost_totals[k]["event_count"] += 1
        cost_totals[k]["total_amount"] += e["amount"]
    agg_cost = [
        {"server": k[0], "currency": k[1], **v} for k, v in sorted(cost_totals.items())
    ]

    return {
        "agg_monthly": agg_monthly,
        "agg_by_system": agg_by_system,
        "agg_by_error_type": agg_by_error_type,
        "agg_cost": agg_cost,
    }


def generate(servers_root: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    base_css = (TEMPLATES_DIR / "base.css").read_text()
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

    events = load_all_events(servers_root)
    servers = sorted({e["server"] for e in events})

    for e in events:
        e["detail_href"] = f"event_detail_{safe_uuid_dirname(e['event_uuid'])}.html"

    index_tpl = env.get_template("index.html")
    (out_dir / "index.html").write_text(
        index_tpl.render(events=events, servers=servers, base_css=base_css, **aggregate(events))
    )

    detail_tpl = env.get_template("event_detail.html")
    for e in events:
        messages, meta = load_detail(e["_db_path"], e["event_uuid"])
        content_path = find_content_xml(servers_root, e["server"], e["event_uuid"])
        raw_xml = content_path.read_text() if content_path else ""
        (out_dir / e["detail_href"]).write_text(
            detail_tpl.render(event=e, messages=messages, meta=meta, raw_xml=raw_xml, base_css=base_css)
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
