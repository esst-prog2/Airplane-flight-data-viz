-- Idempotent transform: raw.state_snapshot -> staging.state_position / staging.rejects.
-- Safe to re-run: the processed range is derived from what is already committed
-- in the two staging tables (no separate checkpoint table), and the whole run
-- is one statement, so a failure mid-run leaves nothing partially written.
--
-- Run with: SELECT * FROM staging.ingest_snapshots();

CREATE OR REPLACE FUNCTION staging.ingest_snapshots()
RETURNS TABLE (accepted bigint, rejected bigint, watermark_from bigint, watermark_to bigint)
LANGUAGE plpgsql
AS $$
DECLARE
    v_watermark   bigint;
    v_max_raw_id  bigint;
    v_accepted    bigint;
    v_rejected    bigint;
BEGIN
    SELECT GREATEST(
        COALESCE((SELECT max(source_raw_id) FROM staging.state_position), 0),
        COALESCE((SELECT max(source_raw_id) FROM staging.rejects), 0)
    ) INTO v_watermark;

    SELECT max(id) INTO v_max_raw_id FROM raw.state_snapshot;

    IF v_max_raw_id IS NULL OR v_max_raw_id <= v_watermark THEN
        RETURN QUERY SELECT 0::bigint, 0::bigint, v_watermark, COALESCE(v_max_raw_id, v_watermark);
        RETURN;
    END IF;

    CREATE TEMP TABLE _batch ON COMMIT DROP AS
    SELECT
        r.id AS source_raw_id,
        r.api_time,
        NULLIF(trim(r.payload ->> 0), '') AS icao24,
        NULLIF(trim(r.payload ->> 1), '') AS callsign,
        (r.payload ->> 3)::bigint AS time_position_epoch,
        (r.payload ->> 5)::double precision AS longitude,
        (r.payload ->> 6)::double precision AS latitude,
        (r.payload ->> 7)::double precision AS baro_altitude,
        (r.payload ->> 8)::boolean AS on_ground
    FROM raw.state_snapshot r
    WHERE r.id > v_watermark AND r.id <= v_max_raw_id;

    -- Rule 1: missing icao24
    INSERT INTO staging.rejects (source_raw_id, reason)
    SELECT source_raw_id, 'missing_icao24'
    FROM _batch
    WHERE icao24 IS NULL;

    -- Rule 2: missing position
    INSERT INTO staging.rejects (source_raw_id, reason)
    SELECT source_raw_id, 'missing_position'
    FROM _batch
    WHERE icao24 IS NOT NULL
      AND (latitude IS NULL OR longitude IS NULL);

    -- Rule 3: missing time_position
    INSERT INTO staging.rejects (source_raw_id, reason)
    SELECT source_raw_id, 'missing_time_position'
    FROM _batch
    WHERE icao24 IS NOT NULL
      AND latitude IS NOT NULL AND longitude IS NOT NULL
      AND time_position_epoch IS NULL;

    -- Rule 4: impossible coordinate
    INSERT INTO staging.rejects (source_raw_id, reason)
    SELECT source_raw_id, 'impossible_coordinate'
    FROM _batch
    WHERE icao24 IS NOT NULL
      AND latitude IS NOT NULL AND longitude IS NOT NULL
      AND time_position_epoch IS NOT NULL
      AND (
          latitude < -90 OR latitude > 90
          OR longitude < -180 OR longitude > 180
          OR (latitude = 0 AND longitude = 0)
      );

    -- Everything else: valid, flagged where suspect, deduplicated on (icao24, time_position)
    INSERT INTO staging.state_position (
        source_raw_id, icao24, callsign, time_position, latitude, longitude,
        baro_altitude, on_ground,
        altitude_missing, altitude_implausible, callsign_missing, position_stale
    )
    SELECT
        source_raw_id,
        icao24,
        callsign,
        to_timestamp(time_position_epoch),
        latitude,
        longitude,
        baro_altitude,
        on_ground,
        baro_altitude IS NULL,
        baro_altitude IS NOT NULL AND baro_altitude > 18288,
        callsign IS NULL,
        (api_time - time_position_epoch) > 1800
    FROM _batch
    WHERE icao24 IS NOT NULL
      AND latitude IS NOT NULL AND longitude IS NOT NULL
      AND time_position_epoch IS NOT NULL
      AND NOT (
          latitude < -90 OR latitude > 90
          OR longitude < -180 OR longitude > 180
          OR (latitude = 0 AND longitude = 0)
      )
    ON CONFLICT (icao24, time_position) DO NOTHING;

    SELECT count(*) INTO v_accepted
    FROM staging.state_position
    WHERE source_raw_id > v_watermark AND source_raw_id <= v_max_raw_id;

    SELECT count(*) INTO v_rejected
    FROM staging.rejects
    WHERE source_raw_id > v_watermark AND source_raw_id <= v_max_raw_id;

    RETURN QUERY SELECT v_accepted, v_rejected, v_watermark, v_max_raw_id;
END;
$$;
