"""
Land an OpenSky aircraft-catalogue CSV in raw.aircraft_catalog, unchanged.

    python scripts/load_aircraft_catalog.py path/to/aircraft-database-complete-YYYY-MM.csv

The file is quoted with apostrophes, not double quotes, and has exactly the
32 columns below; a different header stops the load instead of guessing.
A file whose SHA-256 was already loaded is refused, so a re-run cannot
double the table. The whole load is one transaction.
"""

import hashlib
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

EXPECTED_HEADER = [
    "icao24", "timestamp", "acars", "adsb", "built", "categoryDescription",
    "country", "engines", "firstFlightDate", "firstSeen", "icaoAircraftClass",
    "lineNumber", "manufacturerIcao", "manufacturerName", "model", "modes",
    "nextReg", "notes", "operator", "operatorCallsign", "operatorIata",
    "operatorIcao", "owner", "prevReg", "regUntil", "registered",
    "registration", "selCal", "serialNumber", "status", "typecode", "vdl",
]
TABLE_COLUMNS = [
    "icao24", "source_timestamp", "acars", "adsb", "built", "categorydescription",
    "country", "engines", "firstflightdate", "firstseen", "icaoaircraftclass",
    "linenumber", "manufacturericao", "manufacturername", "model", "modes",
    "nextreg", "notes", "operator", "operatorcallsign", "operatoriata",
    "operatoricao", "owner", "prevreg", "reguntil", "registered",
    "registration", "selcal", "serialnumber", "status", "typecode", "vdl",
]
APOSTROPHE = "'"


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_header(path):
    with open(path, encoding="utf-8") as f:
        first_line = f.readline().rstrip("\r\n")
    return [name.strip(APOSTROPHE) for name in first_line.split(",")]


def load(path, database_url):
    path = Path(path)
    header = read_header(path)
    if header != EXPECTED_HEADER:
        raise SystemExit(
            f"unexpected header in {path.name}: "
            f"missing {sorted(set(EXPECTED_HEADER) - set(header))}, "
            f"extra {sorted(set(header) - set(EXPECTED_HEADER))}"
        )
    digest = sha256_of(path)
    column_list = ", ".join(TABLE_COLUMNS)
    copy_sql = (
        f"COPY _catalog_in ({column_list}) "
        # an apostrophe as an SQL literal is written with four quotes
        "FROM STDIN WITH (FORMAT csv, HEADER true, QUOTE '''')"
    )

    with psycopg.connect(database_url) as conn:
        already = conn.execute(
            "SELECT id, loaded_at FROM raw.aircraft_catalog_load WHERE source_sha256 = %s",
            (digest,),
        ).fetchone()
        if already:
            raise SystemExit(
                f"{path.name} is already loaded (load {already[0]} at {already[1]}); nothing done"
            )

        load_id = conn.execute(
            "INSERT INTO raw.aircraft_catalog_load (source_file, source_sha256, row_count) "
            "VALUES (%s, %s, 0) RETURNING id",
            (path.name, digest),
        ).fetchone()[0]

        with conn.cursor() as cur:
            # load_id is not in the file, so stream into a temp table first.
            cur.execute(
                "CREATE TEMP TABLE _catalog_in (LIKE raw.aircraft_catalog) ON COMMIT DROP"
            )
            cur.execute("ALTER TABLE _catalog_in DROP COLUMN load_id")
            with cur.copy(copy_sql) as copy, open(path, "rb") as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    copy.write(block)
            cur.execute(
                f"INSERT INTO raw.aircraft_catalog (load_id, {column_list}) "
                f"SELECT %s, {column_list} FROM _catalog_in",
                (load_id,),
            )
            rows = cur.rowcount
        conn.execute(
            "UPDATE raw.aircraft_catalog_load SET row_count = %s WHERE id = %s",
            (rows, load_id),
        )
    return load_id, rows


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    loaded_id, loaded_rows = load(sys.argv[1], os.environ["DATABASE_URL"])
    print(f"load {loaded_id}: {loaded_rows} rows landed in raw.aircraft_catalog")
