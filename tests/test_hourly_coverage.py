"""
A test would go red if the hourly coverage check reported an hour as
fully covered when it actually had fewer than 28 real polls landed in
raw.state_snapshot.

Expected values (23 full hours of 337 total) are NOT computed by this
test. They come from sql/spike/collector_coverage.sql, run once on
2026-09-30 against the fixed window below -- see PLANNING_LOG.md,
2026-10-07 entries. That window is entirely in the past and
raw.state_snapshot is append-only, so re-running the same query against
it must always return the same numbers.
"""

import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

WINDOW_START = "2026-09-16 08:13:30.369095+00"
WINDOW_END = "2026-09-30 08:13:30.369095+00"

EXPECTED_TOTAL_HOURS = 337
EXPECTED_FULL_HOURS = 23


def test_hourly_coverage_matches_the_spike():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT total_hours, full_hours FROM staging.hourly_coverage(%s, %s)",
                (WINDOW_START, WINDOW_END),
            )
            total_hours, full_hours = cur.fetchone()

    assert total_hours == EXPECTED_TOTAL_HOURS
    assert full_hours == EXPECTED_FULL_HOURS
