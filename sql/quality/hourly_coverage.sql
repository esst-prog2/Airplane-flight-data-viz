-- Hourly collector coverage: a permanent, callable version of the check
-- sql/spike/collector_coverage.sql ran ad hoc on 2026-09-30.
--
-- An hour is "fully covered" when raw.state_snapshot has at least
-- p_min_polls distinct api_time polls in it (expected ~30 at one poll
-- per 120s -- see run_loop.py's INTERVAL constant).
--
-- Run with: SELECT * FROM staging.hourly_coverage(window_start, window_end);

CREATE OR REPLACE FUNCTION staging.hourly_coverage(
    p_window_start timestamptz,
    p_window_end   timestamptz,
    p_min_polls    int DEFAULT 28
)
RETURNS TABLE (total_hours bigint, full_hours bigint, pct_full_hours numeric)
LANGUAGE sql
STABLE
AS $$
    WITH all_hours AS (
        SELECT generate_series(
                   date_trunc('hour', p_window_start),
                   date_trunc('hour', p_window_end),
                   interval '1 hour'
               ) AS hour_bucket
    ),
    hourly_polls AS (
        SELECT
            date_trunc('hour', r.fetched_at) AS hour_bucket,
            count(DISTINCT r.api_time)       AS poll_count
        FROM raw.state_snapshot r
        WHERE r.fetched_at >= p_window_start AND r.fetched_at < p_window_end
        GROUP BY 1
    ),
    hour_coverage AS (
        SELECT
            ah.hour_bucket,
            (coalesce(hp.poll_count, 0) >= p_min_polls) AS full_hour
        FROM all_hours ah
        LEFT JOIN hourly_polls hp ON hp.hour_bucket = ah.hour_bucket
    )
    SELECT
        count(*)                                                        AS total_hours,
        count(*) FILTER (WHERE full_hour)                               AS full_hours,
        round(100.0 * count(*) FILTER (WHERE full_hour) / count(*), 2)  AS pct_full_hours
    FROM hour_coverage;
$$;
