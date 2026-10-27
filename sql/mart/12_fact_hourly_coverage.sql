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
