-- mart.fact_flight_transit: aggregate fact, one row per continuous pass of an
-- aircraft through the box (consecutive observations at most 600 s apart). Insert-only
-- and closed-only: a transit is inserted only once its last observation is more than
-- 600 s behind the live edge, and rows are never updated afterwards (so no is_closed
-- column and exit keys are NOT NULL). Truncated transits are kept and flagged. The
-- load and closing functions are added in a later file.

CREATE TABLE IF NOT EXISTS mart.fact_flight_transit (
    flight_transit_sk          BIGSERIAL PRIMARY KEY,
    aircraft_sk                BIGINT  NOT NULL REFERENCES mart.dim_aircraft (aircraft_sk),
    region_sk                  INTEGER NOT NULL REFERENCES mart.dim_region (region_sk),
    entry_date_sk_utc          INTEGER NOT NULL REFERENCES mart.dim_date (date_sk),
    entry_date_sk_local        INTEGER NOT NULL REFERENCES mart.dim_date (date_sk),
    entry_time_of_day_sk_utc   INTEGER NOT NULL REFERENCES mart.dim_time_of_day (time_sk),
    entry_time_of_day_sk_local INTEGER NOT NULL REFERENCES mart.dim_time_of_day (time_sk),
    exit_date_sk_utc           INTEGER NOT NULL REFERENCES mart.dim_date (date_sk),
    exit_date_sk_local         INTEGER NOT NULL REFERENCES mart.dim_date (date_sk),
    icao24                     CHAR(6)       NOT NULL,
    callsign                   VARCHAR(8),
    first_seen_at              TIMESTAMPTZ   NOT NULL,
    last_seen_at               TIMESTAMPTZ   NOT NULL,
    snapshot_count             INTEGER       NOT NULL CHECK (snapshot_count > 0),
    duration_minutes           NUMERIC(10,2) NOT NULL CHECK (duration_minutes >= 0),
    distance_km                NUMERIC(10,2) NOT NULL CHECK (distance_km >= 0),
    max_altitude_m             REAL,
    min_altitude_m             REAL,
    avg_altitude_m             REAL,
    max_velocity_mps           REAL,
    avg_velocity_mps           REAL,
    is_start_truncated         BOOLEAN  NOT NULL,
    is_end_truncated           BOOLEAN  NOT NULL,
    segmentation_gap_s         SMALLINT NOT NULL DEFAULT 600,
    built_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (icao24, first_seen_at),
    CHECK (last_seen_at >= first_seen_at)
);

CREATE INDEX IF NOT EXISTS ix_fft_entry_utc   ON mart.fact_flight_transit (entry_date_sk_utc);
CREATE INDEX IF NOT EXISTS ix_fft_entry_local ON mart.fact_flight_transit (entry_date_sk_local);
CREATE INDEX IF NOT EXISTS ix_fft_aircraft    ON mart.fact_flight_transit (aircraft_sk);
CREATE INDEX IF NOT EXISTS ix_fft_icao_last   ON mart.fact_flight_transit (icao24, last_seen_at);
