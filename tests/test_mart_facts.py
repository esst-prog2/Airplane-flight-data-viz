"""
Tests for the mart fact loads on invented data in a throwaway database
(tests/conftest.py). Every expected value is worked out by hand.

A position is seeded into both raw.state_snapshot (full 17-element OpenSky
payload) and staging.state_position, mirroring what the real pipeline leaves
for the mart load to read.
"""

import json

import psycopg
import pytest

# a base reported time; all offsets are seconds from here
T0 = 1_800_000_000  # 2027-01-15 08:00:00 UTC


def seed_catalogue_aircraft(db, icao24, **attrs):
    db.execute(
        "INSERT INTO raw.aircraft_catalog_load (id, source_file, source_sha256, row_count) "
        "VALUES (1, 'test', 'test-sha', 0) ON CONFLICT DO NOTHING"
    )
    cols = ["icao24", "load_id"] + list(attrs.keys())
    vals = [icao24, 1] + list(attrs.values())
    ph = ", ".join(["%s"] * len(cols))
    db.execute(f"INSERT INTO staging.aircraft ({', '.join(cols)}) VALUES ({ph})", vals)


def land(db, raw_id, icao24, tp_epoch, lat=47.5, lon=19.0, callsign="TEST",
         on_ground=False, baro=10000.0, api_time=None):
    """One observed position, into raw (payload) and staging."""
    payload = [None] * 17
    payload[0] = icao24
    payload[1] = callsign
    payload[2] = "Testland"
    payload[3] = tp_epoch
    payload[4] = tp_epoch
    payload[5] = lon
    payload[6] = lat
    payload[7] = baro
    payload[8] = on_ground
    payload[9] = 200.0
    payload[10] = 90.0
    payload[11] = 0.0
    payload[13] = baro + 100
    payload[14] = "1000"
    payload[16] = 0
    db.execute(
        "INSERT INTO raw.state_snapshot (id, fetched_at, api_time, payload) "
        "VALUES (%s, to_timestamp(%s), %s, %s) ON CONFLICT DO NOTHING",
        (raw_id, api_time if api_time is not None else tp_epoch,
         api_time if api_time is not None else tp_epoch, json.dumps(payload)),
    )
    db.execute(
        "INSERT INTO staging.state_position "
        "(source_raw_id, icao24, callsign, time_position, latitude, longitude, "
        " baro_altitude, on_ground, altitude_missing, altitude_implausible, "
        " callsign_missing, position_stale) "
        "VALUES (%s,%s,%s, to_timestamp(%s), %s,%s,%s,%s, false,false,false,false) "
        "ON CONFLICT (icao24, time_position) DO NOTHING",
        (raw_id, icao24, callsign, tp_epoch, lat, lon, baro, on_ground),
    )


def load_dims(db):
    db.execute("SELECT mart.load_dim_date('2026-01-01','2027-12-31')")
    db.execute("SELECT mart.load_dim_time_of_day()")
    db.execute("SELECT mart.load_dim_region()")      # needs a raw row to exist
    db.execute("SELECT mart.load_dim_aircraft()")


def test_position_dedup_and_idempotency(db):
    # two overlapping polls report the same aircraft at the same reported time
    land(db, 1, "aaaaaa", T0, api_time=T0)
    land(db, 2, "aaaaaa", T0, api_time=T0 + 5)   # staging dedup keeps one
    load_dims(db)

    assert db.execute("SELECT mart.load_fact_position_snapshot()").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM mart.fact_position_snapshot").fetchone()[0] == 1
    # the fact's own load is idempotent
    assert db.execute("SELECT mart.load_fact_position_snapshot()").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM mart.fact_position_snapshot").fetchone()[0] == 1


def test_position_of_uncatalogued_aircraft_points_to_unknown_member(db):
    land(db, 1, "ffffff", T0)   # not seeded into staging.aircraft
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")
    row = db.execute(
        "SELECT aircraft_sk, icao24 FROM mart.fact_position_snapshot WHERE icao24 = 'ffffff'"
    ).fetchone()
    assert row == (0, "ffffff")


def test_position_keys_split_utc_and_local_across_midnight(db):
    # 2026-07-01 23:30 UTC is 2026-07-02 01:30 local (CEST, +2h)
    tp = 1782948600   # 2026-07-01 23:30:00 UTC
    land(db, 1, "aaaaaa", tp)
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")
    row = db.execute(
        "SELECT snapshot_date_sk_utc, snapshot_date_sk_local, "
        "snapshot_time_of_day_sk_utc, snapshot_time_of_day_sk_local "
        "FROM mart.fact_position_snapshot WHERE icao24 = 'aaaaaa'"
    ).fetchone()
    assert row == (20260701, 20260702, 23 * 60 + 30, 1 * 60 + 30)


def test_transit_600s_gap_stays_one_601s_splits(db):
    # aircraft A: t0, t0+600 -> one transit; aircraft B: t0, t0+601 -> two transits
    land(db, 1, "aaaaaa", T0)
    land(db, 2, "aaaaaa", T0 + 600)
    land(db, 3, "bbbbbb", T0)
    land(db, 4, "bbbbbb", T0 + 601)
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")
    db.execute("SELECT mart.load_fact_flight_transit(true)")   # p_final: ignore the live edge

    assert db.execute(
        "SELECT count(*) FROM mart.fact_flight_transit WHERE icao24 = 'aaaaaa'"
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT count(*) FROM mart.fact_flight_transit WHERE icao24 = 'bbbbbb'"
    ).fetchone()[0] == 2


def test_transit_of_uncatalogued_aircraft_is_kept(db):
    land(db, 1, "ffffff", T0)
    land(db, 2, "ffffff", T0 + 120)
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")
    db.execute("SELECT mart.load_fact_flight_transit(true)")
    row = db.execute(
        "SELECT aircraft_sk, snapshot_count FROM mart.fact_flight_transit WHERE icao24 = 'ffffff'"
    ).fetchone()
    assert row == (0, 2)


def test_transit_closed_only_holds_the_live_edge_then_inserts_once(db):
    # aircraft A finishes at T0+120, which is the live edge -> held back
    land(db, 1, "aaaaaa", T0)
    land(db, 2, "aaaaaa", T0 + 120)
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")
    assert db.execute("SELECT mart.load_fact_flight_transit()").fetchone()[0] == 0

    # a later position for B pushes the live edge well past A's last observation
    land(db, 3, "bbbbbb", T0 + 2000)
    db.execute("SELECT mart.load_fact_position_snapshot()")
    assert db.execute("SELECT mart.load_fact_flight_transit()").fetchone()[0] == 1   # A, now closed
    # B is still within 600 s of the live edge -> still held; re-run adds nothing
    assert db.execute("SELECT mart.load_fact_flight_transit()").fetchone()[0] == 0
    assert db.execute(
        "SELECT count(*) FROM mart.fact_flight_transit WHERE icao24 = 'aaaaaa'"
    ).fetchone()[0] == 1


def test_transit_crossing_midnight_is_dated_by_entry(db):
    # enters 2026-06-30 23:58 UTC, leaves 2026-07-01 00:02 UTC (240 s gap: one transit)
    enter = 1782863880   # 2026-06-30 23:58:00 UTC
    land(db, 1, "aaaaaa", enter)
    land(db, 2, "aaaaaa", enter + 4 * 60)   # 00:02 next day
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")
    db.execute("SELECT mart.load_fact_flight_transit(true)")
    row = db.execute(
        "SELECT entry_date_sk_utc, exit_date_sk_utc FROM mart.fact_flight_transit WHERE icao24 = 'aaaaaa'"
    ).fetchone()
    assert row == (20260630, 20260701)
    # a daily count by entry date puts it on 30 June only
    assert db.execute(
        "SELECT count(*) FROM mart.fact_flight_transit WHERE entry_date_sk_utc = 20260630"
    ).fetchone()[0] == 1


def test_coverage_generates_a_row_for_an_hour_with_no_polls(db):
    # dense polls in hour H (28+ snapshots), nothing in hour H+1, polls again in H+2.
    # Must be in the past: coverage only generates completed hours up to now().
    base = 1789459200  # 2026-09-15 08:00:00 UTC, on an hour boundary
    for i in range(30):
        land(db, 100 + i, "aaaaaa", base + i * 120, api_time=base + i * 120)
    # skip hour H+1 entirely
    for i in range(30):
        land(db, 300 + i, "aaaaaa", base + 7200 + i * 120, api_time=base + 7200 + i * 120)
    load_dims(db)
    db.execute("SELECT mart.load_fact_hourly_coverage()")

    rows = {
        r[0]: (r[1], r[2])
        for r in db.execute(
            "SELECT extract(epoch FROM hour_start_utc)::bigint, distinct_snapshots, is_fully_covered "
            "FROM mart.fact_hourly_coverage ORDER BY hour_start_utc"
        )
    }
    assert rows[base] == (30, True)          # covered hour
    assert rows[base + 3600] == (0, False)   # the empty hour still has a row
    assert rows[base + 7200] == (30, True)
