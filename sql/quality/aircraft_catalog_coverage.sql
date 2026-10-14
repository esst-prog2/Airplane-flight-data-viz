-- How much of the observed traffic the catalogue can describe.
-- Counted two ways, because they answer different questions:
--   aircraft_*  : distinct icao24 seen in the window (how many aircraft)
--   positions_* : staging.state_position rows in the window (how much traffic;
--                 an aircraft that flew a lot counts more)
-- "in_catalog" = icao24 exists in staging.aircraft;
-- "with_typecode" = ... and its typecode is known.
--
-- Run with: SELECT * FROM staging.aircraft_catalog_coverage(window_start, window_end);

CREATE OR REPLACE FUNCTION staging.aircraft_catalog_coverage(
    p_window_start timestamptz,
    p_window_end   timestamptz
)
RETURNS TABLE (
    aircraft_seen           bigint,
    aircraft_in_catalog     bigint,
    aircraft_with_typecode  bigint,
    positions_seen          bigint,
    positions_in_catalog    bigint,
    positions_with_typecode bigint
)
LANGUAGE sql
STABLE
AS $$
    WITH seen AS (
        SELECT sp.icao24, count(*) AS n
        FROM staging.state_position sp
        WHERE sp.time_position >= p_window_start AND sp.time_position < p_window_end
        GROUP BY sp.icao24
    )
    SELECT
        count(*)::bigint,
        count(a.icao24)::bigint,
        count(a.typecode)::bigint,
        coalesce(sum(s.n), 0)::bigint,
        coalesce(sum(s.n) FILTER (WHERE a.icao24 IS NOT NULL), 0)::bigint,
        coalesce(sum(s.n) FILTER (WHERE a.typecode IS NOT NULL), 0)::bigint
    FROM seen s
    LEFT JOIN staging.aircraft a ON a.icao24 = s.icao24;
$$;
