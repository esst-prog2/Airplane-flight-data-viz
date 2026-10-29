-- mart.dim_time_of_day: one row per minute of a 24-hour day (smart key hour*60+minute),
-- static, date-independent. Referenced by facts as a UTC minute and a local minute.
-- is_peak_traffic marks the local hours 10:00-18:00 inclusive: the hours whose median
-- distinct-aircraft presence reaches >=80% of the daily peak in the measured curve
-- (PLANNING_LOG 2026-10-29, re-derived from the earlier 06-09/16-19 placeholder). It is
-- a LOCAL-time flag -- join it through the local time-of-day key, not the UTC one.
-- The load is an upsert (DO UPDATE), so re-running it re-syncs every row to this
-- definition; the attributes are fully derived from time_sk, so there is no key to keep stable.

CREATE TABLE IF NOT EXISTS mart.dim_time_of_day (
    time_sk          INTEGER PRIMARY KEY CHECK (time_sk BETWEEN 0 AND 1439),
    hour_24          SMALLINT    NOT NULL,
    minute           SMALLINT    NOT NULL,
    quarter_hour     SMALLINT    NOT NULL,
    time_label       CHAR(5)     NOT NULL,
    hour_label       CHAR(5)     NOT NULL,
    time_of_day      VARCHAR(10) NOT NULL,
    time_of_day_hu   VARCHAR(10) NOT NULL,
    is_business_hour BOOLEAN     NOT NULL,
    is_peak_traffic  BOOLEAN     NOT NULL,
    shift_label      VARCHAR(10) NOT NULL
);

CREATE OR REPLACE FUNCTION mart.load_dim_time_of_day()
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_count bigint;
BEGIN
    INSERT INTO mart.dim_time_of_day (
        time_sk, hour_24, minute, quarter_hour, time_label, hour_label,
        time_of_day, time_of_day_hu, is_business_hour, is_peak_traffic, shift_label
    )
    SELECT
        m,
        (m / 60)::smallint,
        (m % 60)::smallint,
        ((m % 60) / 15)::smallint,
        to_char(make_time(m / 60, m % 60, 0), 'HH24:MI'),
        to_char(make_time(m / 60, 0, 0), 'HH24:MI'),
        CASE
            WHEN m / 60 BETWEEN 0  AND 5  THEN 'night'
            WHEN m / 60 BETWEEN 6  AND 11 THEN 'morning'
            WHEN m / 60 BETWEEN 12 AND 17 THEN 'afternoon'
            ELSE 'evening'
        END,
        CASE
            WHEN m / 60 BETWEEN 0  AND 5  THEN 'éjszaka'
            WHEN m / 60 BETWEEN 6  AND 11 THEN 'délelőtt'
            WHEN m / 60 BETWEEN 12 AND 17 THEN 'délután'
            ELSE 'este'
        END,
        (m / 60) BETWEEN 8 AND 16,
        (m / 60) BETWEEN 10 AND 18,
        CASE
            WHEN m / 60 BETWEEN 6  AND 13 THEN 'day'
            WHEN m / 60 BETWEEN 14 AND 21 THEN 'evening'
            ELSE 'night'
        END
    FROM generate_series(0, 1439) AS g(m)
    ON CONFLICT (time_sk) DO UPDATE SET
        hour_24          = EXCLUDED.hour_24,
        minute           = EXCLUDED.minute,
        quarter_hour     = EXCLUDED.quarter_hour,
        time_label       = EXCLUDED.time_label,
        hour_label       = EXCLUDED.hour_label,
        time_of_day      = EXCLUDED.time_of_day,
        time_of_day_hu   = EXCLUDED.time_of_day_hu,
        is_business_hour = EXCLUDED.is_business_hour,
        is_peak_traffic  = EXCLUDED.is_peak_traffic,
        shift_label      = EXCLUDED.shift_label;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;
