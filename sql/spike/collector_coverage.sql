-- Spike: what fraction of the last two weeks did the collector actually cover,
-- and how many aircraft gaps survive once the contaminated hours are removed?
--
-- An hour is "fully covered" when raw.state_snapshot has at least 28 distinct
-- api_time polls in it (expected ~30 at one poll/120s). A gap between two
-- consecutive staging.state_position rows for the same icao24 "survives" only
-- if every hour it spans is fully covered; gaps touching any under-covered
-- hour are discarded as collector-downtime artifacts, not real aircraft gaps.
--
-- Run with: docker exec flights_db psql -U flights -d flights -f /path/to/this/file
-- (or paste into psql). Read-only: touches raw.state_snapshot and
-- staging.state_position only.

WITH bounded AS (
    SELECT
        max(fetched_at) - interval '14 days' AS window_start,
        max(fetched_at)                      AS window_end
    FROM raw.state_snapshot
),
all_hours AS (
    SELECT generate_series(
               date_trunc('hour', b.window_start),
               date_trunc('hour', b.window_end),
               interval '1 hour'
           ) AS hour_bucket
    FROM bounded b
),
hourly_polls AS (
    SELECT
        date_trunc('hour', r.fetched_at) AS hour_bucket,
        count(DISTINCT r.api_time)       AS poll_count
    FROM raw.state_snapshot r, bounded b
    WHERE r.fetched_at >= b.window_start AND r.fetched_at < b.window_end
    GROUP BY 1
),
hour_coverage AS (
    SELECT
        ah.hour_bucket,
        coalesce(hp.poll_count, 0)                  AS poll_count,
        (coalesce(hp.poll_count, 0) >= 28)          AS full_hour
    FROM all_hours ah
    LEFT JOIN hourly_polls hp ON hp.hour_bucket = ah.hour_bucket
),
coverage_summary AS (
    SELECT
        count(*)                                   AS total_hours,
        count(*) FILTER (WHERE full_hour)          AS full_hours,
        round(100.0 * count(*) FILTER (WHERE full_hour) / count(*), 2) AS pct_full_hours
    FROM hour_coverage
),
positions AS (
    SELECT
        sp.icao24,
        sp.time_position,
        lag(sp.time_position) OVER (PARTITION BY sp.icao24 ORDER BY sp.time_position) AS prev_time_position
    FROM staging.state_position sp, bounded b
    WHERE sp.time_position >= b.window_start AND sp.time_position < b.window_end
),
gaps AS (
    SELECT icao24, prev_time_position, time_position
    FROM positions
    WHERE prev_time_position IS NOT NULL
),
surviving_gaps AS (
    SELECT g.*
    FROM gaps g
    WHERE NOT EXISTS (
        SELECT 1
        FROM generate_series(
                 date_trunc('hour', g.prev_time_position),
                 date_trunc('hour', g.time_position),
                 interval '1 hour'
             ) AS h(hour_bucket)
        LEFT JOIN hour_coverage hc ON hc.hour_bucket = h.hour_bucket
        WHERE hc.full_hour IS NOT TRUE
    )
)
SELECT
    (SELECT window_start FROM bounded)                    AS window_start,
    (SELECT window_end FROM bounded)                       AS window_end,
    (SELECT total_hours FROM coverage_summary)             AS total_hours,
    (SELECT full_hours FROM coverage_summary)              AS full_hours,
    (SELECT pct_full_hours FROM coverage_summary)          AS pct_hours_with_ge28_polls,
    (SELECT count(*) FROM gaps)                            AS total_gaps,
    (SELECT count(*) FROM surviving_gaps)                  AS surviving_gaps;
