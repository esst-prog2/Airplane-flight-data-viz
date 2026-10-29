"""
Data access behind one interface, so the five views serve both forms of the
dashboard unchanged (see the dashboard-distribution spec). Chunk 1 adds the
`DataSource` protocol and `DbSource`, the direct read-only database backend —
the live fallback and what the API wraps. `ApiSource` (live) and `SnapshotSource`
(offline) arrive in later chunks.

Every method returns plain Python values (dicts / lists) so the same results
serialize to JSON for the API and feed the Streamlit views directly.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Protocol, runtime_checkable

from . import queries


def day_sk(day: dt.date) -> int:
    """The mart.dim_date surrogate key for a calendar day (YYYYMMDD)."""
    return day.year * 10000 + day.month * 100 + day.day


def sk_to_date(sk: int | None) -> dt.date | None:
    """Inverse of `day_sk`: a YYYYMMDD surrogate key back to a date."""
    if sk is None:
        return None
    sk = int(sk)
    return dt.date(sk // 10000, (sk // 100) % 100, sk % 100)


@runtime_checkable
class DataSource(Protocol):
    """What every view needs, independent of where the data comes from."""

    def date_range(self) -> tuple[dt.date | None, dt.date | None]:
        """Earliest and latest local day that has data (None, None if empty)."""

    def kpis(self) -> dict[str, Any]:
        """Dataset-wide headline totals for the KPI band."""

    def day_map(self, day: dt.date) -> list[dict[str, Any]]:
        """H3 cells for the day: {h3, lat, lon, count}."""

    def day_curve(self, day: dt.date) -> list[dict[str, Any]]:
        """24 rows {hour, aircraft}: distinct aircraft present per local hour."""

    def day_coverage(self, day: dt.date) -> list[dict[str, Any]]:
        """24 rows {hour, is_fully_covered, positions, observed} for the day."""

    def day_breakdown(self, day: dt.date) -> dict[str, list[dict[str, Any]]]:
        """{by_type: [...], by_country: [...]} for the day; no operator, no owner."""


class DbSource:
    """Reads the mart directly over psycopg. In production it connects as the
    read-only `flights_ro` role; it is also the live fallback when the API is
    down, and the backend the API itself wraps."""

    def __init__(self, dsn: str, h3_resolution: int = 5) -> None:
        self._dsn = dsn
        self._res = h3_resolution

    def _rows(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple]:
        import psycopg  # imported lazily so the module loads without a DB driver

        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchall()

    def date_range(self) -> tuple[dt.date | None, dt.date | None]:
        (lo, hi), = self._rows(queries.DATE_RANGE_SQL)
        return (sk_to_date(lo), sk_to_date(hi))

    def kpis(self) -> dict[str, Any]:
        row, = self._rows(queries.KPIS_SQL)
        keys = ("positions", "transits", "distinct_aircraft", "days", "catalog_coverage_pct")
        return {k: (int(v) if v is not None else None) for k, v in zip(keys, row)}

    def day_curve(self, day: dt.date) -> list[dict[str, Any]]:
        got = {int(h): int(n) for h, n in self._rows(queries.DAY_CURVE_SQL, {"day_sk": day_sk(day)})}
        return [{"hour": h, "aircraft": got.get(h, 0)} for h in range(24)]

    def day_coverage(self, day: dt.date) -> list[dict[str, Any]]:
        got = {int(h): (bool(fc), int(pos)) for h, fc, pos in
               self._rows(queries.DAY_COVERAGE_SQL, {"day": day})}
        out = []
        for h in range(24):
            fc, pos = got.get(h, (False, 0))
            out.append({"hour": h, "is_fully_covered": fc, "positions": pos, "observed": h in got})
        return out

    def day_breakdown(self, day: dt.date) -> dict[str, list[dict[str, Any]]]:
        p = {"day_sk": day_sk(day)}
        return {
            "by_type": [{"label": t, "positions": int(n)}
                        for t, n in self._rows(queries.DAY_TYPE_SQL, p)],
            "by_country": [{"label": c, "positions": int(n)}
                           for c, n in self._rows(queries.DAY_COUNTRY_SQL, p)],
        }

    def day_map(self, day: dt.date) -> list[dict[str, Any]]:
        points = self._rows(queries.DAY_POSITIONS_SQL, {"day_sk": day_sk(day)})
        return bin_h3(points, self._res)


def bin_h3(points: list[tuple], resolution: int) -> list[dict[str, Any]]:
    """Aggregate (lat, lon) rows into H3 cells, returning each cell's id, centre
    and count. Pre-aggregating here keeps the raw points out of every response."""
    import h3  # h3 v4 API; imported lazily so non-map callers need no h3

    counts: dict[str, int] = {}
    for lat, lon in points:
        cell = h3.latlng_to_cell(float(lat), float(lon), resolution)
        counts[cell] = counts.get(cell, 0) + 1

    cells = []
    for cell, n in counts.items():
        lat, lon = h3.cell_to_latlng(cell)
        cells.append({"h3": cell, "lat": lat, "lon": lon, "count": n})
    return cells
