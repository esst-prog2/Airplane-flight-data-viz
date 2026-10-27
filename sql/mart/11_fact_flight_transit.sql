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

-- Gaps-and-islands segmentation at 600 s over mart.fact_position_snapshot.
-- p_final = false (the hourly run): insert only transits whose last observation is
--   more than 600 s behind the live edge; leave open ones for a later run; never update.
-- p_final = true (the one-off closing run after collection ends): insert the remaining
--   open transits too, flagged is_end_truncated.
-- Incremental: only positions newer than each aircraft's latest last_seen_at already in
-- the fact are reconsidered, so closed transits are never touched.
CREATE OR REPLACE FUNCTION mart.load_fact_flight_transit(p_final boolean DEFAULT false)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_live_edge timestamptz;
    v_start     timestamptz;
    v_region    int;
    v_count     bigint;
BEGIN
    SET LOCAL work_mem = '256MB';
    SELECT max(time_position_utc), min(time_position_utc)
      INTO v_live_edge, v_start FROM mart.fact_position_snapshot;
    IF v_live_edge IS NULL THEN RETURN 0; END IF;
    SELECT region_sk INTO v_region FROM mart.dim_region WHERE is_current LIMIT 1;

    INSERT INTO mart.fact_flight_transit (
        aircraft_sk, region_sk,
        entry_date_sk_utc, entry_date_sk_local,
        entry_time_of_day_sk_utc, entry_time_of_day_sk_local,
        exit_date_sk_utc, exit_date_sk_local,
        icao24, callsign, first_seen_at, last_seen_at,
        snapshot_count, duration_minutes, distance_km,
        max_altitude_m, min_altitude_m, avg_altitude_m, max_velocity_mps, avg_velocity_mps,
        is_start_truncated, is_end_truncated, segmentation_gap_s
    )
    WITH new_pos AS (
        SELECT p.icao24, p.time_position_utc AS tp, p.latitude, p.longitude,
               p.baro_altitude_m, p.velocity_mps, p.on_ground, p.is_altitude_implausible,
               p.callsign
        FROM mart.fact_position_snapshot p
        LEFT JOIN (
            SELECT icao24, max(last_seen_at) AS mx
            FROM mart.fact_flight_transit GROUP BY icao24
        ) t ON t.icao24 = p.icao24
        WHERE t.mx IS NULL OR p.time_position_utc > t.mx
    ),
    flagged AS (
        SELECT *,
               CASE WHEN lag(tp) OVER w IS NULL
                     OR tp - lag(tp) OVER w > interval '600 seconds'
                    THEN 1 ELSE 0 END AS isnew
        FROM new_pos
        WINDOW w AS (PARTITION BY icao24 ORDER BY tp)
    ),
    islands AS (
        SELECT *, sum(isnew) OVER (PARTITION BY icao24 ORDER BY tp) AS grp
        FROM flagged
    ),
    stepped AS (
        SELECT *,
               lag(latitude)  OVER w2 AS plat,
               lag(longitude) OVER w2 AS plon,
               lag(on_ground) OVER w2 AS p_on_ground
        FROM islands
        WINDOW w2 AS (PARTITION BY icao24, grp ORDER BY tp)
    ),
    callsigns AS (
        SELECT DISTINCT ON (icao24, grp) icao24, grp, callsign
        FROM (
            SELECT icao24, grp, callsign, count(*) AS n, min(tp) AS first_tp
            FROM islands
            WHERE callsign IS NOT NULL AND callsign <> ''
            GROUP BY icao24, grp, callsign
        ) c
        ORDER BY icao24, grp, n DESC, first_tp ASC
    ),
    agg AS (
        SELECT
            s.icao24, s.grp,
            min(s.tp) AS first_seen_at,
            max(s.tp) AS last_seen_at,
            count(*)  AS snapshot_count,
            round((extract(epoch FROM max(s.tp) - min(s.tp)) / 60)::numeric, 2) AS duration_minutes,
            round(coalesce(sum(
                CASE WHEN s.plat IS NOT NULL AND NOT s.on_ground AND NOT s.p_on_ground
                     THEN 6371.0 * 2 * asin(sqrt(
                            power(sin(radians(s.latitude - s.plat) / 2), 2)
                          + cos(radians(s.plat)) * cos(radians(s.latitude))
                          * power(sin(radians(s.longitude - s.plon) / 2), 2)))
                     ELSE 0 END), 0)::numeric, 2) AS distance_km,
            max(s.baro_altitude_m) FILTER (WHERE NOT s.is_altitude_implausible) AS max_altitude_m,
            min(s.baro_altitude_m) FILTER (WHERE NOT s.is_altitude_implausible) AS min_altitude_m,
            avg(s.baro_altitude_m) FILTER (WHERE NOT s.is_altitude_implausible)::real AS avg_altitude_m,
            max(s.velocity_mps) AS max_velocity_mps,
            avg(s.velocity_mps)::real AS avg_velocity_mps
        FROM stepped s
        GROUP BY s.icao24, s.grp
    )
    SELECT
        coalesce(d.aircraft_sk, 0),
        v_region,
        to_char(a.first_seen_at AT TIME ZONE 'UTC', 'YYYYMMDD')::int,
        to_char(a.first_seen_at AT TIME ZONE 'Europe/Budapest', 'YYYYMMDD')::int,
        extract(hour FROM a.first_seen_at AT TIME ZONE 'UTC')::int * 60
            + extract(minute FROM a.first_seen_at AT TIME ZONE 'UTC')::int,
        extract(hour FROM a.first_seen_at AT TIME ZONE 'Europe/Budapest')::int * 60
            + extract(minute FROM a.first_seen_at AT TIME ZONE 'Europe/Budapest')::int,
        to_char(a.last_seen_at AT TIME ZONE 'UTC', 'YYYYMMDD')::int,
        to_char(a.last_seen_at AT TIME ZONE 'Europe/Budapest', 'YYYYMMDD')::int,
        a.icao24,
        cs.callsign,
        a.first_seen_at,
        a.last_seen_at,
        a.snapshot_count,
        a.duration_minutes,
        a.distance_km,
        a.max_altitude_m, a.min_altitude_m, a.avg_altitude_m,
        a.max_velocity_mps, a.avg_velocity_mps,
        (a.first_seen_at < v_start + interval '600 seconds'),
        (a.last_seen_at >= v_live_edge - interval '600 seconds'),
        600
    FROM agg a
    LEFT JOIN mart.dim_aircraft d ON d.icao24 = a.icao24
    LEFT JOIN callsigns cs ON cs.icao24 = a.icao24 AND cs.grp = a.grp
    WHERE p_final OR a.last_seen_at < v_live_edge - interval '600 seconds'
    ON CONFLICT (icao24, first_seen_at) DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- One-off closing run after collection ends: inserts the still-open transits,
-- flagged is_end_truncated. A thin wrapper over the load with p_final = true.
CREATE OR REPLACE FUNCTION mart.close_open_transits()
RETURNS bigint LANGUAGE sql AS $$
    SELECT mart.load_fact_flight_transit(true);
$$;
