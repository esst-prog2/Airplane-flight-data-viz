"""
Unit tests for staging.ingest_snapshots() on invented data.

Every number below is made up and the expected result worked out by hand,
not copied from running the code. The `db` fixture (tests/conftest.py) gives each test a throwaway database
in the local Postgres with the repo's own SQL loaded, so neither the dev
data nor the VPS is touched.

Raw payload layout (OpenSky state vector): index 0 icao24, 1 callsign,
3 time_position, 5 longitude, 6 latitude, 7 baro_altitude, 8 on_ground.
"""

import json

POLL_1 = 1_800_000_000
POLL_2 = 1_800_000_010
T = 1_799_999_990  # a position reported a few seconds before POLL_1


def state(icao24, lat, lon, time_position=T, callsign="TEST1", baro=10000.0):
    payload = [None] * 17
    payload[0] = icao24
    payload[1] = callsign
    payload[3] = time_position
    payload[5] = lon
    payload[6] = lat
    payload[7] = baro
    payload[8] = False
    return payload


def land(conn, api_time, states):
    """Write one poll to raw.state_snapshot the way ingest.py does."""
    for s in states:
        conn.execute(
            "INSERT INTO raw.state_snapshot (api_time, payload) VALUES (%s, %s)",
            (api_time, json.dumps(s)),
        )


def run(conn):
    return conn.execute("SELECT accepted, rejected FROM staging.ingest_snapshots()").fetchone()


def test_record_without_latitude_is_rejected_and_the_rest_are_kept(db):
    # three aircraft, the middle one has no latitude
    land(db, POLL_1, [
        state("aaaaaa", lat=47.5, lon=19.0),
        state("bbbbbb", lat=None, lon=19.5),
        state("cccccc", lat=48.0, lon=17.0),
    ])

    accepted, rejected = run(db)

    # by hand: 3 records, 1 missing a position -> 2 kept, 1 rejected
    assert (accepted, rejected) == (2, 1)

    reasons = db.execute(
        """SELECT r.reason, s.payload ->> 0
           FROM staging.rejects r JOIN raw.state_snapshot s ON s.id = r.source_raw_id"""
    ).fetchall()
    assert reasons == [("missing_position", "bbbbbb")]

    kept = {row[0] for row in db.execute("SELECT icao24 FROM staging.state_position")}
    assert kept == {"aaaaaa", "cccccc"}


def test_same_aircraft_same_timestamp_in_two_polls_is_one_row(db):
    # poll 1 and poll 2 overlap: both report aaaaaa at time T;
    # poll 2 also reports aaaaaa at a new time T+10
    land(db, POLL_1, [state("aaaaaa", lat=47.5, lon=19.0, time_position=T)])
    land(db, POLL_2, [
        state("aaaaaa", lat=47.5, lon=19.0, time_position=T),
        state("aaaaaa", lat=47.6, lon=19.1, time_position=T + 10),
    ])

    run(db)

    # by hand: 3 raw records but only 2 distinct (icao24, time_position) pairs
    times = [
        row[0]
        for row in db.execute(
            "SELECT extract(epoch FROM time_position)::bigint "
            "FROM staging.state_position WHERE icao24 = 'aaaaaa' ORDER BY 1"
        )
    ]
    assert times == [T, T + 10]


def test_running_twice_adds_nothing(db):
    land(db, POLL_1, [
        state("aaaaaa", lat=47.5, lon=19.0),
        state("bbbbbb", lat=None, lon=19.5),
    ])

    run(db)
    counts_after_first = db.execute(
        "SELECT (SELECT count(*) FROM staging.state_position),"
        "       (SELECT count(*) FROM staging.rejects)"
    ).fetchone()

    accepted, rejected = run(db)

    assert (accepted, rejected) == (0, 0)
    assert counts_after_first == (1, 1)
    assert db.execute(
        "SELECT (SELECT count(*) FROM staging.state_position),"
        "       (SELECT count(*) FROM staging.rejects)"
    ).fetchone() == counts_after_first
