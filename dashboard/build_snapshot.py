"""
Build the frozen SQLite snapshot for the offline dashboard form (see the
dashboard-distribution spec). It reads the mart through `DbSource` (the live
Postgres), computes the same per-day aggregates the views use, and writes them
into a single SQLite file. The file holds no raw position rows and no `owner`,
so it stays a few MB and is safe to commit and host publicly.

    python -m dashboard.build_snapshot --output flights_snapshot.sqlite

The DSN comes from --dsn or DATABASE_URL. `SnapshotSource` reads the result back.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3

from .datasource import DbSource

_SCHEMA = """
CREATE TABLE meta (
    date_min TEXT, date_max TEXT, default_day TEXT,
    kpi_positions INTEGER, kpi_transits INTEGER, kpi_distinct_aircraft INTEGER,
    kpi_days INTEGER, kpi_catalog_coverage_pct INTEGER
);
CREATE TABLE day_map (day TEXT, h3 TEXT, lat REAL, lon REAL, count INTEGER);
CREATE TABLE day_curve (day TEXT, hour INTEGER, aircraft INTEGER);
CREATE TABLE day_coverage (day TEXT, hour INTEGER, is_fully_covered INTEGER,
                           positions INTEGER, observed INTEGER);
CREATE TABLE day_breakdown (day TEXT, kind TEXT, label TEXT, positions INTEGER);
CREATE INDEX ix_map_day ON day_map (day);
CREATE INDEX ix_curve_day ON day_curve (day);
CREATE INDEX ix_coverage_day ON day_coverage (day);
CREATE INDEX ix_breakdown_day ON day_breakdown (day);
"""


def build(dsn: str, output_path: str, h3_resolution: int = 5) -> int:
    """Write the snapshot; return the number of days written."""
    src = DbSource(dsn, h3_resolution=h3_resolution)
    lo, hi = src.date_range()

    if os.path.exists(output_path):
        os.remove(output_path)
    conn = sqlite3.connect(output_path)
    try:
        conn.executescript(_SCHEMA)

        kpis = src.kpis()
        default = src.default_day()
        conn.execute(
            "INSERT INTO meta VALUES (?,?,?,?,?,?,?,?)",
            (
                lo.isoformat() if lo else None,
                hi.isoformat() if hi else None,
                default.isoformat() if default else None,
                kpis.get("positions"), kpis.get("transits"),
                kpis.get("distinct_aircraft"), kpis.get("days"),
                kpis.get("catalog_coverage_pct"),
            ),
        )
        if lo is None:
            conn.commit()
            return 0

        n_days = (hi - lo).days + 1
        for i in range(n_days):
            day = lo + dt.timedelta(days=i)
            d = day.isoformat()
            conn.executemany(
                "INSERT INTO day_map VALUES (?,?,?,?,?)",
                [(d, c["h3"], c["lat"], c["lon"], c["count"]) for c in src.day_map(day)],
            )
            conn.executemany(
                "INSERT INTO day_curve VALUES (?,?,?)",
                [(d, r["hour"], r["aircraft"]) for r in src.day_curve(day)],
            )
            conn.executemany(
                "INSERT INTO day_coverage VALUES (?,?,?,?,?)",
                [(d, r["hour"], int(r["is_fully_covered"]), r["positions"], int(r["observed"]))
                 for r in src.day_coverage(day)],
            )
            bd = src.day_breakdown(day)
            conn.executemany(
                "INSERT INTO day_breakdown VALUES (?,?,?,?)",
                [(d, "type", r["label"], r["positions"]) for r in bd["by_type"]]
                + [(d, "country", r["label"], r["positions"]) for r in bd["by_country"]],
            )
        conn.commit()
        return n_days
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the offline dashboard SQLite snapshot.")
    ap.add_argument("--output", default="flights_snapshot.sqlite")
    ap.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--h3-resolution", type=int, default=5)
    args = ap.parse_args()
    if not args.dsn:
        ap.error("no DSN: pass --dsn or set DATABASE_URL")
    days = build(args.dsn, args.output, args.h3_resolution)
    size_mb = os.path.getsize(args.output) / 1e6
    print(f"wrote {args.output}: {days} days, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
