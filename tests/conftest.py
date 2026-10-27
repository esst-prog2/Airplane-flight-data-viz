"""
Shared fixtures: a throwaway database in the local dev Postgres, loaded
with the repo's own SQL (init, transform, quality) and dropped afterwards.
Neither the dev data nor the VPS is touched; the fixture refuses to run
against any host other than the local machine.
"""

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict, make_conninfo

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SQL_FILES = (
    sorted((ROOT / "sql" / "init").glob("*.sql"))
    + sorted((ROOT / "sql" / "transform").glob("*.sql"))
    + sorted((ROOT / "sql" / "quality").glob("*.sql"))
    + sorted((ROOT / "sql" / "mart").glob("*.sql"))
    + sorted((ROOT / "sql" / "ops").glob("*.sql"))
)


@pytest.fixture
def db_url():
    """Connection URL of a fresh database with the repo's schema loaded."""
    url = os.environ["DATABASE_URL"]
    host = conninfo_to_dict(url).get("host")
    assert host in ("localhost", "127.0.0.1"), (
        f"refusing to create a test database on {host!r}; "
        "these tests only run against the local dev Postgres"
    )
    # "localhost" tries IPv6 first on Windows and waits ~15 s per connection
    # before falling back; go straight to IPv4.
    admin_url = make_conninfo(url, host="127.0.0.1")

    name = f"test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    test_url = make_conninfo(admin_url, dbname=name)
    try:
        with psycopg.connect(test_url, autocommit=True) as conn:
            for path in SQL_FILES:
                conn.execute(path.read_text(encoding="utf-8"))
        yield test_url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def db(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        yield conn
