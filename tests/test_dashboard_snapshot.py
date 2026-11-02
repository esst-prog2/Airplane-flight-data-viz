"""
Tests for the frozen SQLite snapshot (dashboard/build_snapshot.py) and
SnapshotSource: build a snapshot from a throwaway database, then confirm it
reads back identically to DbSource and carries no raw positions and no owner.
"""

import datetime as dt
import sqlite3

import pytest

from test_mart_facts import seed_catalogue_aircraft, land, load_dims, T0

from dashboard import build_snapshot
from dashboard.datasource import DbSource, SnapshotSource

DAY = dt.date(2027, 1, 15)   # T0 = 2027-01-15 08:00 UTC -> 09:00 local, same day


@pytest.fixture
def snapshot_path(db, db_url, tmp_path):
    seed_catalogue_aircraft(
        db, "aaaaaa", registration="HA-TST", typecode="B738", model="737-800",
        category_description="Large", country="Hungary", operator="Test Air",
        operator_icao="TST", owner="A Private Owner",
    )
    land(db, 1, "aaaaaa", T0, lat=47.5, lon=19.0)
    land(db, 2, "aaaaaa", T0 + 120, lat=47.6, lon=19.1)
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")

    path = str(tmp_path / "snap.sqlite")
    build_snapshot.build(db_url, path)
    return path


def test_snapshot_reads_back_identically_to_dbsource(snapshot_path, db_url):
    snap = SnapshotSource(snapshot_path)
    dbs = DbSource(db_url)
    assert snap.date_range() == dbs.date_range()
    assert snap.default_day() == dbs.default_day()
    assert snap.kpis() == dbs.kpis()
    assert snap.day_curve(DAY) == dbs.day_curve(DAY)
    assert snap.day_coverage(DAY) == dbs.day_coverage(DAY)
    assert snap.day_breakdown(DAY) == dbs.day_breakdown(DAY)
    key = lambda cells: sorted((c["h3"], c["count"]) for c in cells)
    assert key(snap.day_map(DAY)) == key(dbs.day_map(DAY))


def test_snapshot_carries_no_owner_and_no_raw_positions(snapshot_path):
    conn = sqlite3.connect(snapshot_path)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    # no owner anywhere (table or column names)
    for t in tables:
        assert "owner" not in t.lower()
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        assert all("owner" not in c.lower() for c in cols)
    # the map is binned, not raw: two seeded positions collapse into one cell count 2
    total = conn.execute("SELECT sum(count) FROM day_map").fetchone()[0]
    cells = conn.execute("SELECT count(*) FROM day_map").fetchone()[0]
    assert total == 2 and cells <= 2
    conn.close()
