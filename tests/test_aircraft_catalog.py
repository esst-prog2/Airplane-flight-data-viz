"""
Tests for the aircraft catalogue: loader, cleaning and coverage count.

All data here is invented and every expected number is worked out by hand
from the rows below, not from running the code. Each test gets a throwaway
database from tests/conftest.py. The invented CSV uses the real file's
shape: 32 columns, values quoted with apostrophes.
"""

import csv
import importlib.util
import sys
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "load_aircraft_catalog", ROOT / "scripts" / "load_aircraft_catalog.py"
)
loader = importlib.util.module_from_spec(_spec)
sys.modules["load_aircraft_catalog"] = loader
_spec.loader.exec_module(loader)

T0 = 1_800_000_000


def write_catalog(path, rows, header=None):
    """rows: list of dicts keyed by the file's own column names."""
    header = header or loader.EXPECTED_HEADER
    with open(path, "w", newline="", encoding="utf-8") as f:
        # quote everything, like the real file does for text: an empty value then
        # arrives as an empty string, not as NULL
        w = csv.writer(f, quotechar="'", quoting=csv.QUOTE_ALL)
        w.writerow(header)
        for row in rows:
            w.writerow([row.get(col, "") for col in header])
    return path


# Four invented rows:
#   1. upper-case id, padded registration, apostrophe in the operator name
#   2. valid, but the type code is empty
#   3. only 5 hex digits (a lost leading character) -> must be skipped
#   4. the same aircraft as row 1 once lower-cased -> second copy skipped
CATALOG_ROWS = [
    {"icao24": "AAAAAA", "registration": " HA-XYZ ", "typecode": "A320",
     "manufacturerName": "Airbus", "operator": "Air L'Example", "country": "Hungary"},
    {"icao24": "bbbbbb", "typecode": "", "manufacturerName": "Cessna", "country": "Austria"},
    {"icao24": "0926e", "typecode": "B738"},
    {"icao24": "aaaaaa", "typecode": "A321"},
]


@pytest.fixture
def catalog_file(tmp_path):
    return write_catalog(tmp_path / "catalog.csv", CATALOG_ROWS)


def test_loader_lands_every_row_unchanged_and_refuses_the_same_file_twice(db, db_url, catalog_file):
    load_id, rows = loader.load(catalog_file, db_url)

    assert rows == 4  # all four rows land, including the ones cleaning will skip
    stored = db.execute(
        "SELECT icao24, registration, operator FROM raw.aircraft_catalog "
        "WHERE load_id = %s ORDER BY icao24",
        (load_id,),
    ).fetchall()
    # raw means raw: no lower-casing, no trimming, apostrophe survived the CSV quoting
    assert ("AAAAAA", " HA-XYZ ", "Air L'Example") in stored
    assert db.execute("SELECT row_count FROM raw.aircraft_catalog_load").fetchone() == (4,)

    with pytest.raises(SystemExit, match="already loaded"):
        loader.load(catalog_file, db_url)
    assert db.execute("SELECT count(*) FROM raw.aircraft_catalog").fetchone() == (4,)


def test_loader_stops_on_an_unexpected_header(db, db_url, tmp_path):
    renamed = ["icao" if c == "icao24" else c for c in loader.EXPECTED_HEADER]
    bad = write_catalog(tmp_path / "bad.csv", [], header=renamed)

    with pytest.raises(SystemExit, match="unexpected header"):
        loader.load(bad, db_url)
    assert db.execute("SELECT count(*) FROM raw.aircraft_catalog_load").fetchone() == (0,)


def test_build_aircraft_cleans_and_skips_what_it_cannot_trust(db, db_url, catalog_file):
    loader.load(catalog_file, db_url)

    _load_id, loaded_rows, kept, skipped = db.execute(
        "SELECT * FROM staging.build_aircraft()"
    ).fetchone()

    # by hand: 4 landed; '0926e' is invalid, the second 'aaaaaa' is a duplicate
    assert (loaded_rows, kept, skipped) == (4, 2, 2)
    ids = [r[0] for r in db.execute("SELECT icao24 FROM staging.aircraft ORDER BY icao24")]
    assert ids == ["aaaaaa", "bbbbbb"]

    registration, operator = db.execute(
        "SELECT registration, operator FROM staging.aircraft WHERE icao24 = 'aaaaaa'"
    ).fetchone()
    assert registration == "HA-XYZ"
    assert operator == "Air L'Example"

    # an empty type code is NULL, not an empty string
    assert db.execute(
        "SELECT typecode FROM staging.aircraft WHERE icao24 = 'bbbbbb'"
    ).fetchone() == (None,)


def test_build_aircraft_fails_loudly_when_nothing_was_loaded(db):
    with pytest.raises(psycopg.errors.RaiseException, match="load a catalogue file first"):
        db.execute("SELECT * FROM staging.build_aircraft()")


def test_coverage_counts_aircraft_and_positions_separately(db, db_url, catalog_file):
    loader.load(catalog_file, db_url)
    db.execute("SELECT * FROM staging.build_aircraft()")  # catalogue: aaaaaa (A320), bbbbbb (no type)

    raw_id = db.execute(
        "INSERT INTO raw.state_snapshot (api_time, payload) VALUES (%s, '[]') RETURNING id",
        (T0,),
    ).fetchone()[0]
    # invented traffic: aaaaaa x3, bbbbbb x1, cccccc x2 (cccccc is not in the catalogue)
    seen = [("aaaaaa", 3), ("bbbbbb", 1), ("cccccc", 2)]
    for icao24, n in seen:
        for i in range(n):
            db.execute(
                "INSERT INTO staging.state_position "
                "(source_raw_id, icao24, time_position, latitude, longitude) "
                "VALUES (%s, %s, to_timestamp(%s), 47.5, 19.0)",
                (raw_id, icao24, T0 - 100 + i),
            )

    row = db.execute(
        "SELECT * FROM staging.aircraft_catalog_coverage(to_timestamp(%s), to_timestamp(%s))",
        (T0 - 1000, T0),
    ).fetchone()

    # by hand: 3 aircraft seen, 2 in the catalogue, 1 with a known type;
    #          6 positions seen, 3 + 1 = 4 in the catalogue, 3 with a known type
    assert row == (3, 2, 1, 6, 4, 3)
