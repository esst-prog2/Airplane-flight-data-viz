"""
Tests for the `flights` CLI commands.

These exercise the testable core of each command against the throwaway `db`
fixture (tests/conftest.py), so they touch neither the live API nor the dev/VPS
data. Invented raw rows are landed by hand the way ingest.py does, and the
expected accepted/rejected counts are worked out from the staging reject rules.

Raw payload layout (OpenSky state vector): index 0 icao24, 1 callsign,
3 time_position, 5 longitude, 6 latitude, 7 baro_altitude, 8 on_ground.
"""

import json

import pytest

from flights.cli import _run_step, ingest_once, run_build

T = 1_800_000_000


def _state(icao24, lat, lon, time_position=T - 10):
    payload = [None] * 17
    payload[0] = icao24
    payload[1] = "TEST1"
    payload[3] = time_position
    payload[5] = lon
    payload[6] = lat
    payload[7] = 10000.0
    payload[8] = False
    return payload


def _lander(states):
    """Return a land(conn) callable that writes the given states to raw, like ingest.py."""

    def land(conn):
        for s in states:
            conn.execute(
                "INSERT INTO raw.state_snapshot (api_time, payload) VALUES (%s, %s)",
                (T, json.dumps(s)),
            )

    return land


def test_ingest_once_lands_and_summarises_by_reason(db):
    # four aircraft: two valid, one with no position, one with no icao24
    states = [
        _state("aaaaaa", lat=47.5, lon=19.0),  # valid
        _state("bbbbbb", lat=None, lon=19.5),  # missing position
        _state("cccccc", lat=48.0, lon=17.0),  # valid
        _state(None, lat=47.0, lon=18.0),      # missing icao24
    ]

    summary = ingest_once(db, _lander(states))

    assert summary["landed"] == 4
    assert summary["accepted"] == 2
    assert summary["rejected"] == 2
    assert dict(summary["by_reason"]) == {"missing_position": 1, "missing_icao24": 1}


def test_ingest_once_propagates_a_failed_fetch(db):
    # the collector exits non-zero on an API error; ingest_once must not swallow it
    def boom(_conn):
        raise SystemExit(1)

    with pytest.raises(SystemExit):
        ingest_once(db, boom)


# --- build ---------------------------------------------------------------------

def _land_raw(conn, raw_id, icao24, tp_epoch, lat=47.5, lon=19.0):
    """One observed position into raw only, for the build's staging step to process."""
    payload = [None] * 17
    payload[0] = icao24
    payload[1] = "TEST1"
    payload[3] = tp_epoch
    payload[4] = tp_epoch
    payload[5] = lon
    payload[6] = lat
    payload[7] = 10000.0
    payload[8] = False
    conn.execute(
        "INSERT INTO raw.state_snapshot (id, api_time, payload) VALUES (%s, %s, %s)",
        (raw_id, tp_epoch, json.dumps(payload)),
    )


def _seed_known_aircraft(conn, icao24, typecode):
    conn.execute(
        "INSERT INTO raw.aircraft_catalog_load (id, source_file, source_sha256, row_count) "
        "VALUES (1, 'test', 'test-sha', 0) ON CONFLICT DO NOTHING"
    )
    conn.execute(
        "INSERT INTO staging.aircraft (icao24, load_id, typecode) VALUES (%s, 1, %s)",
        (icao24, typecode),
    )


def _seed_closeable_transit(conn):
    # aircraft A (known type) is observed at T0 and T0+120 -> one closed transit once
    # aircraft B's later observation pushes the live edge past A (so A's transit closes).
    _seed_known_aircraft(conn, "aaaaaa", "B738")
    _land_raw(conn, 1, "aaaaaa", T)
    _land_raw(conn, 2, "aaaaaa", T + 120)
    _land_raw(conn, 3, "bbbbbb", T + 2000)  # uncatalogued -> unknown member


def test_build_with_dims_runs_all_steps_and_summarises(db):
    _seed_closeable_transit(db)

    steps, summary = run_build(db, with_dims=True)

    labels = [label for label, _ in steps]
    assert labels == [
        "dim_date", "dim_time_of_day", "dim_region", "dim_aircraft",
        "staging", "fact_position_snapshot", "fact_flight_transit", "fact_hourly_coverage",
    ]
    counts = dict(steps)
    assert counts["staging"] == 3                 # three raw positions accepted
    assert counts["fact_position_snapshot"] == 3
    assert counts["fact_flight_transit"] == 1     # A closes; B held at the live edge

    # the one closed transit is A, which has a known type (B738)
    assert summary["segments"] == 1
    assert summary["known_type_pct"] == 100.0


def test_build_without_dims_skips_the_dimension_loads(db):
    _seed_closeable_transit(db)
    run_build(db, with_dims=True)  # first build loads everything

    steps, _ = run_build(db, with_dims=False)  # rebuild: dims must be skipped

    labels = [label for label, _ in steps]
    assert labels == [
        "staging", "fact_position_snapshot", "fact_flight_transit", "fact_hourly_coverage",
    ]
    assert all(not lbl.startswith("dim_") for lbl in labels)


def test_build_step_failure_names_the_step(db):
    with pytest.raises(RuntimeError, match=r"build step 'boom' failed"):
        _run_step(db, "boom", "SELECT 1 / 0")
