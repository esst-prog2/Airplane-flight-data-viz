-- mart.fact_hourly_coverage: periodic snapshot fact, one row per UTC hour of the whole
-- collection, including hours with zero polls (generated from the calendar, because raw
-- has no row for an empty hour). UTC keys only (deliberate exception to the UTC/local
-- rule). Two poll measures: distinct_polls (fetched_at) and distinct_snapshots (api_time);
-- is_fully_covered uses distinct_snapshots >= 28. The load function is added in a later file.

CREATE TABLE IF NOT EXISTS mart.fact_hourly_coverage (
    coverage_sk        BIGSERIAL PRIMARY KEY,
    region_sk          INTEGER NOT NULL REFERENCES mart.dim_region (region_sk),
    date_sk            INTEGER NOT NULL REFERENCES mart.dim_date (date_sk),
    time_of_day_sk     INTEGER NOT NULL REFERENCES mart.dim_time_of_day (time_sk)
                       CHECK (time_of_day_sk % 60 = 0),
    hour_start_utc     TIMESTAMPTZ NOT NULL,
    distinct_polls     INTEGER NOT NULL CHECK (distinct_polls >= 0),
    distinct_snapshots INTEGER NOT NULL CHECK (distinct_snapshots >= 0),
    expected_polls     INTEGER NOT NULL,
    positions_landed   INTEGER NOT NULL CHECK (positions_landed >= 0),
    is_fully_covered   BOOLEAN NOT NULL,
    is_partial_hour    BOOLEAN NOT NULL,
    built_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (region_sk, hour_start_utc)
);

CREATE INDEX IF NOT EXISTS ix_fhc_date ON mart.fact_hourly_coverage (date_sk);

-- Generates the completed UTC hours since the last stored hour (never the current,
-- incomplete hour), including hours with zero polls. Two measures: distinct_polls
-- (fetched_at) and distinct_snapshots (api_time); is_fully_covered uses api_time >= 28.
-- Only the first collection hour is flagged partial here; the final partial hour (when
-- collection stops mid-hour) is marked by a one-off step at collection end.
-- date_trunc uses an explicit UTC zone so the hour buckets do not depend on the session.
CREATE OR REPLACE FUNCTION mart.load_fact_hourly_coverage()
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_first  timestamptz;
    v_last   timestamptz;
    v_from   timestamptz;
    v_region int;
    v_count  bigint;
BEGIN
    SELECT date_trunc('hour', min(fetched_at), 'UTC') INTO v_first FROM raw.state_snapshot;
    IF v_first IS NULL THEN RETURN 0; END IF;

    v_last := date_trunc('hour', now(), 'UTC') - interval '1 hour';   -- last completed hour
    SELECT region_sk INTO v_region FROM mart.dim_region WHERE is_current LIMIT 1;

    SELECT coalesce(max(hour_start_utc) + interval '1 hour', v_first)
      INTO v_from FROM mart.fact_hourly_coverage;
    v_from := greatest(v_from, v_first);
    IF v_from > v_last THEN RETURN 0; END IF;

    INSERT INTO mart.fact_hourly_coverage (
        region_sk, date_sk, time_of_day_sk, hour_start_utc,
        distinct_polls, distinct_snapshots, expected_polls, positions_landed,
        is_fully_covered, is_partial_hour
    )
    SELECT
        v_region,
        to_char(h AT TIME ZONE 'UTC', 'YYYYMMDD')::int,
        extract(hour FROM h AT TIME ZONE 'UTC')::int * 60,
        h,
        coalesce(c.distinct_polls, 0),
        coalesce(c.distinct_snapshots, 0),
        30,
        coalesce(c.positions_landed, 0),
        coalesce(c.distinct_snapshots, 0) >= 28,
        (h = v_first)
    FROM generate_series(v_from, v_last, interval '1 hour') AS g(h)
    LEFT JOIN (
        SELECT date_trunc('hour', fetched_at, 'UTC') AS hr,
               count(DISTINCT fetched_at) AS distinct_polls,
               count(DISTINCT api_time)   AS distinct_snapshots,
               count(*)                   AS positions_landed
        FROM raw.state_snapshot
        WHERE fetched_at >= v_from AND fetched_at < v_last + interval '1 hour'
        GROUP BY 1
    ) c ON c.hr = h
    ON CONFLICT (region_sk, hour_start_utc) DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;
