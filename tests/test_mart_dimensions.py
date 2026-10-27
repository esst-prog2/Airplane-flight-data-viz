"""
Tests for the mart dimensions, on invented data in a throwaway database
(tests/conftest.py). Every expected value is worked out by hand.
"""

import psycopg
import pytest


def seed_catalogue(db, rows):
    """rows: list of dicts with staging.aircraft column names (icao24 required)."""
    db.execute(
        "INSERT INTO raw.aircraft_catalog_load (id, source_file, source_sha256, row_count) "
        "VALUES (1, 'test', 'test-sha', 0) ON CONFLICT DO NOTHING"
    )
    for r in rows:
        cols = list(r.keys()) + ["load_id"]
        vals = list(r.values()) + [1]
        placeholders = ", ".join(["%s"] * len(cols))
        db.execute(
            f"INSERT INTO staging.aircraft ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )


def test_dim_date_marks_dst_switches_holidays_and_smart_key(db):
    db.execute("SELECT mart.load_dim_date('2026-01-01', '2026-12-31')")

    # by hand: clocks go back on 2026-10-25 (to CET, +60) and forward on 2026-03-29 (to CEST, +120)
    assert db.execute(
        "SELECT is_dst_switch_day, is_dst_local, utc_offset_minutes_local "
        "FROM mart.dim_date WHERE full_date = '2026-10-25'"
    ).fetchone() == (True, False, 60)
    assert db.execute(
        "SELECT is_dst_switch_day, is_dst_local, utc_offset_minutes_local "
        "FROM mart.dim_date WHERE full_date = '2026-03-29'"
    ).fetchone() == (True, True, 120)

    # Easter Monday 2026 is 6 April; a Hungarian public holiday
    assert db.execute(
        "SELECT is_holiday_hu FROM mart.dim_date WHERE full_date = '2026-04-06'"
    ).fetchone() == (True,)
    # an ordinary weekday is not
    assert db.execute(
        "SELECT is_holiday_hu, is_weekend FROM mart.dim_date WHERE full_date = '2026-04-07'"
    ).fetchone() == (False, False)

    # smart key is YYYYMMDD
    assert db.execute(
        "SELECT date_sk FROM mart.dim_date WHERE full_date = '2026-10-25'"
    ).fetchone() == (20261025,)


def test_dim_time_of_day_has_1440_rows_with_a_smart_key(db):
    db.execute("SELECT mart.load_dim_time_of_day()")
    assert db.execute("SELECT count(*) FROM mart.dim_time_of_day").fetchone() == (1440,)
    # time_sk = hour*60 + minute
    assert db.execute(
        "SELECT hour_24, minute, quarter_hour FROM mart.dim_time_of_day WHERE time_sk = %s",
        (14 * 60 + 35,),
    ).fetchone() == (14, 35, 2)
    # every row obeys the smart-key identity
    assert db.execute(
        "SELECT count(*) FROM mart.dim_time_of_day WHERE time_sk <> hour_24 * 60 + minute"
    ).fetchone() == (0,)


def test_dim_region_matches_the_ingest_bounding_box(db):
    # load_dim_region needs a collection start in raw
    db.execute("INSERT INTO raw.state_snapshot (api_time, payload) VALUES (1800000000, '[]')")
    db.execute("SELECT mart.load_dim_region()")
    row = db.execute(
        "SELECT region_code, bbox_min_latitude, bbox_max_latitude, "
        "bbox_min_longitude, bbox_max_longitude, is_current, valid_to "
        "FROM mart.dim_region WHERE region_sk = 1"
    ).fetchone()
    # bounds are the ingest.py BBOX (lamin 45, lamax 50, lomin 12, lomax 23)
    assert row[0] == "CEU"
    assert (float(row[1]), float(row[2]), float(row[3]), float(row[4])) == (45.0, 50.0, 12.0, 23.0)
    assert row[5] is True and row[6] is None


def test_unknown_member_exists_and_absorbs_missing_attributes(db):
    seed_catalogue(db, [
        {"icao24": "abc123", "typecode": "A320", "operator": None, "country": "Hungary"},
    ])
    db.execute("SELECT mart.load_dim_aircraft()")

    unknown = db.execute(
        "SELECT icao24, operator, type_designator, in_catalog FROM mart.dim_aircraft WHERE aircraft_sk = 0"
    ).fetchone()
    assert unknown == (None, "Unknown", "Unknown", False)

    # a catalogue aircraft with no operator gets 'Unknown', not NULL, and in_catalog TRUE
    ac = db.execute(
        "SELECT operator, in_catalog FROM mart.dim_aircraft WHERE icao24 = 'abc123'"
    ).fetchone()
    assert ac == ("Unknown", True)


def test_no_dimension_text_attribute_is_null(db):
    seed_catalogue(db, [{"icao24": "abc123", "operator": None, "model": None}])
    db.execute("SELECT mart.load_dim_aircraft()")
    # every text attribute is non-null across the whole dimension (sentinel policy)
    assert db.execute(
        "SELECT count(*) FROM mart.dim_aircraft WHERE registration IS NULL OR type_designator IS NULL "
        "OR model IS NULL OR aircraft_category IS NULL OR operator IS NULL OR operator_icao IS NULL "
        "OR owner IS NULL OR registration_country IS NULL"
    ).fetchone() == (0,)


def test_aircraft_surrogate_keys_are_stable_across_a_catalogue_reload(db):
    seed_catalogue(db, [
        {"icao24": "aaaaaa", "operator": "Alpha"},
        {"icao24": "bbbbbb", "operator": "Beta"},
    ])
    db.execute("SELECT mart.load_dim_aircraft()")
    sk_a = db.execute("SELECT aircraft_sk FROM mart.dim_aircraft WHERE icao24 = 'aaaaaa'").fetchone()[0]
    sk_b = db.execute("SELECT aircraft_sk FROM mart.dim_aircraft WHERE icao24 = 'bbbbbb'").fetchone()[0]

    # simulate a catalogue reload: staging.aircraft is rebuilt from scratch,
    # aaaaaa's operator changes, a new aircraft cccccc appears
    db.execute("DELETE FROM staging.aircraft")
    seed_catalogue(db, [
        {"icao24": "aaaaaa", "operator": "Alpha Renamed"},
        {"icao24": "bbbbbb", "operator": "Beta"},
        {"icao24": "cccccc", "operator": "Gamma"},
    ])
    db.execute("SELECT mart.load_dim_aircraft()")

    # existing keys unchanged, attribute overwritten (SCD1), new aircraft gets a fresh key
    assert db.execute("SELECT aircraft_sk FROM mart.dim_aircraft WHERE icao24 = 'aaaaaa'").fetchone()[0] == sk_a
    assert db.execute("SELECT aircraft_sk FROM mart.dim_aircraft WHERE icao24 = 'bbbbbb'").fetchone()[0] == sk_b
    assert db.execute("SELECT operator FROM mart.dim_aircraft WHERE icao24 = 'aaaaaa'").fetchone()[0] == "Alpha Renamed"
    sk_c = db.execute("SELECT aircraft_sk FROM mart.dim_aircraft WHERE icao24 = 'cccccc'").fetchone()[0]
    assert sk_c not in (0, sk_a, sk_b)


def test_load_dim_aircraft_is_idempotent(db):
    seed_catalogue(db, [{"icao24": "aaaaaa", "operator": "Alpha"}])
    db.execute("SELECT mart.load_dim_aircraft()")
    before = db.execute("SELECT count(*) FROM mart.dim_aircraft").fetchone()[0]
    db.execute("SELECT mart.load_dim_aircraft()")
    after = db.execute("SELECT count(*) FROM mart.dim_aircraft").fetchone()[0]
    assert before == after
