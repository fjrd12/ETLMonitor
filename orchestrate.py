"""Toy-demo CLI: runs ETL 1 -> ETL 2 -> ETL 3 -> dashboard generation in order."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dashboard.generate import generate as generate_dashboard
from etl import etl1_land, etl2_monetize, etl3_warehouse


def run(landing_zone: Path, servers_root: Path, resources_root: Path, out_dir: Path) -> None:
    landed = etl1_land.run(landing_zone, servers_root)
    print(f"[etl1] landed {len(landed)} triplet(s)")

    monetized = etl2_monetize.run(servers_root, resources_root)
    print(f"[etl2] monetized {len(monetized)} event(s)")

    warehoused = etl3_warehouse.run(servers_root, resources_root)
    print(f"[etl3] warehoused {warehoused} event(s)")

    rendered = generate_dashboard(servers_root, out_dir)
    print(f"[dashboard] rendered {rendered} event page(s) -> {out_dir / 'index.html'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--landing-zone", type=Path, default=Path("input"))
    parser.add_argument("--servers-root", type=Path, default=Path("servers"))
    parser.add_argument("--resources-root", type=Path, default=Path("resources"))
    parser.add_argument("--out-dir", type=Path, default=Path("dashboard/out"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    run(args.landing_zone, args.servers_root, args.resources_root, args.out_dir)
