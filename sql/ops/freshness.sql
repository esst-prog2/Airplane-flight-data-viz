-- ops.check_freshness: how far the mart lags the raw landing table, so a stalled or
-- failed build chain is noticed before the presentation. Lag is measured on the
-- leading edge (the position fact), not the transit fact, which lags by design.
--   raw_latest  = newest raw.state_snapshot.fetched_at
--   mart_latest = newest fact_position_snapshot.snapshot_time (the fetched_at of the
--                 latest loaded position)
-- is_stale when nothing is loaded yet, or the lag exceeds p_threshold_minutes (default 3 h,
-- PLANNING_LOG 2026-10-27: normal lag is at most ~65 min, so 3 h tolerates one missed run).
-- The function only reports; the alert is sent by deploy/mart_freshness.sh via the webhook.

CREATE OR REPLACE FUNCTION ops.check_freshness(p_threshold_minutes int DEFAULT 180)
RETURNS TABLE (
    raw_latest   timestamptz,
    mart_latest  timestamptz,
    lag_minutes  numeric,
    is_stale     boolean
)
LANGUAGE sql STABLE AS $$
    WITH r AS (SELECT max(fetched_at)   AS raw_latest  FROM raw.state_snapshot),
         m AS (SELECT max(snapshot_time) AS mart_latest FROM mart.fact_position_snapshot)
    SELECT
        r.raw_latest,
        m.mart_latest,
        round((extract(epoch FROM (r.raw_latest - m.mart_latest)) / 60)::numeric, 1),
        m.mart_latest IS NULL
            OR (r.raw_latest - m.mart_latest) > make_interval(mins => p_threshold_minutes)
    FROM r, m;
$$;
