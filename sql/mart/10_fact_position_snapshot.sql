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
