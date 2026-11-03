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

from flights.cli import ingest_once

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
