"""
Per-day aggregation SQL over the mart for the dashboard (see the dashboard-views
and mart-read-api specs). Day selection is by the local date surrogate key
(`snapshot_date_sk_local`, YYYYMMDD); the curve and coverage are in local
Europe/Budapest time. The map query returns the day's raw (lat, lon), which
`DbSource` bins into H3 cells in Python, because the warehouse has no h3-pg
extension — the API and the browser still only ever see aggregated cells.
"""

# min / max local day that has any position (surrogate keys, YYYYMMDD)
DATE_RANGE_SQL = """
    SELECT min(snapshot_date_sk_local), max(snapshot_date_sk_local)
    FROM mart.fact_position_snapshot
"""

# dataset-wide headline totals for the KPI band
KPIS_SQL = """
    SELECT
        (SELECT count(*) FROM mart.fact_position_snapshot),
        (SELECT count(*) FROM mart.fact_flight_transit),
        (SELECT count(DISTINCT aircraft_sk) FROM mart.fact_position_snapshot),
        (SELECT count(DISTINCT snapshot_date_sk_local) FROM mart.fact_position_snapshot),
        (SELECT round(100.0 * count(*) FILTER (WHERE aircraft_sk <> 0)
                      / NULLIF(count(*), 0), 1)
           FROM mart.fact_position_snapshot)
"""

# distinct aircraft present per local hour on the selected day
DAY_CURVE_SQL = """
    SELECT snapshot_time_of_day_sk_local / 60 AS hour,
           count(DISTINCT aircraft_sk) AS aircraft
    FROM mart.fact_position_snapshot
    WHERE snapshot_date_sk_local = %(day_sk)s
    GROUP BY 1
    ORDER BY 1
"""

# hourly coverage for the selected local day (hour_start_utc is converted to local)
DAY_COVERAGE_SQL = """
    SELECT extract(hour FROM (hour_start_utc AT TIME ZONE 'Europe/Budapest'))::int AS hour,
           bool_and(is_fully_covered) AS is_fully_covered,
           sum(positions_landed)      AS positions
    FROM mart.fact_hourly_coverage
    WHERE (hour_start_utc AT TIME ZONE 'Europe/Budapest')::date = %(day)s
    GROUP BY 1
    ORDER BY 1
"""

# top aircraft types on the selected day (unknown member shows as 'Unknown', kept honestly)
DAY_TYPE_SQL = """
    SELECT a.type_designator AS label, count(*) AS positions
    FROM mart.fact_position_snapshot f
    JOIN mart.dim_aircraft a USING (aircraft_sk)
    WHERE f.snapshot_date_sk_local = %(day_sk)s
    GROUP BY 1
    ORDER BY count(*) DESC, 1
    LIMIT 15
"""

# top registration countries on the selected day
DAY_COUNTRY_SQL = """
    SELECT a.registration_country AS label, count(*) AS positions
    FROM mart.fact_position_snapshot f
    JOIN mart.dim_aircraft a USING (aircraft_sk)
    WHERE f.snapshot_date_sk_local = %(day_sk)s
    GROUP BY 1
    ORDER BY count(*) DESC, 1
    LIMIT 15
"""

# raw positions for the selected day, binned into H3 cells by DbSource
DAY_POSITIONS_SQL = """
    SELECT latitude, longitude
    FROM mart.fact_position_snapshot
    WHERE snapshot_date_sk_local = %(day_sk)s
"""
