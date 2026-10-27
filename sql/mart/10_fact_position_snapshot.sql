-- mart.fact_position_snapshot: atomic transaction fact, one row per de-duplicated
-- observed position (icao24, time_position). Loaded from staging.state_position and,
-- for the columns staging never kept, from raw.state_snapshot.payload joined on
-- source_raw_id (documented layering exception, PLANNING_LOG 2026-10-27). Date/time
-- keys are derived from time_position (event time), not fetched_at. The load function
-- is added in a later file.

CREATE TABLE IF NOT EXISTS mart.fact_position_snapshot (
    snapshot_sk                   BIGSERIAL PRIMARY KEY,
    aircraft_sk                   BIGINT  NOT NULL REFERENCES mart.dim_aircraft (aircraft_sk),
    region_sk                     INTEGER NOT NULL REFERENCES mart.dim_region (region_sk),
    snapshot_date_sk_utc          INTEGER NOT NULL REFERENCES mart.dim_date (date_sk),
    snapshot_date_sk_local        INTEGER NOT NULL REFERENCES mart.dim_date (date_sk),
    snapshot_time_of_day_sk_utc   INTEGER NOT NULL REFERENCES mart.dim_time_of_day (time_sk),
    snapshot_time_of_day_sk_local INTEGER NOT NULL REFERENCES mart.dim_time_of_day (time_sk),
    icao24                        CHAR(6)      NOT NULL,
    callsign                      VARCHAR(8),
    squawk                        VARCHAR(4),
    position_source               SMALLINT,
    origin_country                VARCHAR(100),
    raw_id                        BIGINT       NOT NULL,
    time_position_utc             TIMESTAMPTZ  NOT NULL,
    last_contact_utc              TIMESTAMPTZ,
    snapshot_time                 TIMESTAMPTZ  NOT NULL,
    latitude                      NUMERIC(9,6) NOT NULL,
    longitude                     NUMERIC(9,6) NOT NULL,
    baro_altitude_m               REAL,
    geo_altitude_m                REAL,
    velocity_mps                  REAL,
    true_track_deg                REAL,
    vertical_rate_mps             REAL,
    on_ground                     BOOLEAN NOT NULL,
    is_altitude_missing           BOOLEAN NOT NULL,
    is_altitude_implausible       BOOLEAN NOT NULL,
    is_position_stale             BOOLEAN NOT NULL,
    is_callsign_missing           BOOLEAN NOT NULL,
    loaded_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (icao24, time_position_utc)        -- also serves the stitching scan
);

CREATE INDEX IF NOT EXISTS ix_fps_date_utc   ON mart.fact_position_snapshot (snapshot_date_sk_utc);
CREATE INDEX IF NOT EXISTS ix_fps_date_local ON mart.fact_position_snapshot (snapshot_date_sk_local);
CREATE INDEX IF NOT EXISTS ix_fps_aircraft   ON mart.fact_position_snapshot (aircraft_sk);
CREATE INDEX IF NOT EXISTS ix_fps_raw_id     ON mart.fact_position_snapshot (raw_id);
CREATE INDEX IF NOT EXISTS ix_fps_time_pos   ON mart.fact_position_snapshot (time_position_utc);

-- Incremental, idempotent load. Watermark = max(raw_id) already in the fact (no
-- checkpoint table). Reads accepted staging rows above the watermark and joins raw
-- for the columns staging never kept (payload indices: 2 origin_country, 4 last_contact,
-- 9 velocity, 10 true_track, 11 vertical_rate, 13 geo_altitude, 14 squawk, 16 position_source)
-- and for fetched_at (snapshot_time). Date/time keys come from time_position (event time).
CREATE OR REPLACE FUNCTION mart.load_fact_position_snapshot()
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_watermark bigint;
    v_region    int;
    v_count     bigint;
BEGIN
    SELECT coalesce(max(raw_id), 0) INTO v_watermark FROM mart.fact_position_snapshot;
    SELECT region_sk INTO v_region FROM mart.dim_region WHERE is_current LIMIT 1;
    IF v_region IS NULL THEN
        RAISE EXCEPTION 'mart.dim_region has no current region: load dimensions first';
    END IF;

    INSERT INTO mart.fact_position_snapshot (
        aircraft_sk, region_sk,
        snapshot_date_sk_utc, snapshot_date_sk_local,
        snapshot_time_of_day_sk_utc, snapshot_time_of_day_sk_local,
        icao24, callsign, squawk, position_source, origin_country,
        raw_id, time_position_utc, last_contact_utc, snapshot_time,
        latitude, longitude, baro_altitude_m, geo_altitude_m,
        velocity_mps, true_track_deg, vertical_rate_mps, on_ground,
        is_altitude_missing, is_altitude_implausible, is_position_stale, is_callsign_missing
    )
    SELECT
        coalesce(d.aircraft_sk, 0),
        v_region,
        to_char(sp.time_position AT TIME ZONE 'UTC', 'YYYYMMDD')::int,
        to_char(sp.time_position AT TIME ZONE 'Europe/Budapest', 'YYYYMMDD')::int,
        extract(hour   FROM sp.time_position AT TIME ZONE 'UTC')::int * 60
            + extract(minute FROM sp.time_position AT TIME ZONE 'UTC')::int,
        extract(hour   FROM sp.time_position AT TIME ZONE 'Europe/Budapest')::int * 60
            + extract(minute FROM sp.time_position AT TIME ZONE 'Europe/Budapest')::int,
        sp.icao24,
        sp.callsign,
        nullif(r.payload ->> 14, ''),
        (r.payload ->> 16)::smallint,
        r.payload ->> 2,
        sp.source_raw_id,
        sp.time_position,
        CASE WHEN r.payload ->> 4 IS NULL THEN NULL
             ELSE to_timestamp((r.payload ->> 4)::double precision) END,
        r.fetched_at,
        sp.latitude,
        sp.longitude,
        sp.baro_altitude,
        (r.payload ->> 13)::real,
        (r.payload ->> 9)::real,
        (r.payload ->> 10)::real,
        (r.payload ->> 11)::real,
        sp.on_ground,
        sp.altitude_missing,
        sp.altitude_implausible,
        sp.position_stale,
        sp.callsign_missing
    FROM staging.state_position sp
    JOIN raw.state_snapshot r ON r.id = sp.source_raw_id
    LEFT JOIN mart.dim_aircraft d ON d.icao24 = sp.icao24
    WHERE sp.source_raw_id > v_watermark
    ON CONFLICT (icao24, time_position_utc) DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;
