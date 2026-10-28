"""
Tests for ops.check_freshness on invented data in a throwaway database
(tests/conftest.py). Reuses the mart fact seeding helpers.
"""

from test_mart_facts import land, load_dims, T0


def _load_one_position(db, raw_id, icao24, tp_epoch):
    land(db, raw_id, icao24, tp_epoch, api_time=tp_epoch)
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")


def test_freshness_healthy_when_mart_is_current(db):
    # the only raw row is also the latest loaded position -> lag ~ 0
    _load_one_position(db, 1, "aaaaaa", T0)
    row = db.execute("SELECT lag_minutes, is_stale FROM ops.check_freshness(180)").fetchone()
    assert row[0] == 0.0
    assert row[1] is False


def test_freshness_stale_when_raw_runs_ahead_of_the_mart(db):
    _load_one_position(db, 1, "aaaaaa", T0)
    # a newer raw poll lands but is NOT loaded into the mart -> the mart falls behind
    land(db, 2, "aaaaaa", T0 + 4 * 3600, api_time=T0 + 4 * 3600)   # 4 h newer
    row = db.execute("SELECT lag_minutes, is_stale FROM ops.check_freshness(180)").fetchone()
    assert row[0] == 240.0            # 4 hours
    assert row[1] is True             # over the 180-minute threshold

    # a wider threshold would tolerate the same lag
    assert db.execute("SELECT is_stale FROM ops.check_freshness(300)").fetchone()[0] is False


def test_freshness_stale_when_nothing_is_loaded(db):
    # raw has data but the mart is empty
    land(db, 1, "aaaaaa", T0, api_time=T0)
    load_dims(db)   # dimensions only, no fact load
    row = db.execute("SELECT mart_latest, is_stale FROM ops.check_freshness(180)").fetchone()
    assert row[0] is None
    assert row[1] is True
