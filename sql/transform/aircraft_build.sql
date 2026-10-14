-- Rebuilds staging.aircraft from the most recent catalogue load.
-- Cleaning rules (nothing is guessed):
--   * icao24 is trimmed and lower-cased; it must then be exactly 6 hex digits.
--     Rows that are not (in the 2025-08 file, 29 values that lost a leading
--     character) are skipped, not padded -- padding would be a guess.
--   * trimmed empty strings become NULL.
--   * if an icao24 appears twice in one load, one of the copies is kept
--     (which one is not defined; the 2025-08 file has no duplicates).
-- Safe to re-run: it is one transaction that replaces the whole table.
--
-- Run with: SELECT * FROM staging.build_aircraft();

CREATE OR REPLACE FUNCTION staging.build_aircraft()
RETURNS TABLE (load_id bigint, loaded_rows bigint, kept bigint, skipped bigint)
LANGUAGE plpgsql
AS $$
DECLARE
    v_load   bigint;
    v_total  bigint;
    v_kept   bigint;
BEGIN
    SELECT l.id INTO v_load FROM raw.aircraft_catalog_load l ORDER BY l.id DESC LIMIT 1;
    IF v_load IS NULL THEN
        RAISE EXCEPTION 'raw.aircraft_catalog_load is empty: load a catalogue file first';
    END IF;

    DELETE FROM staging.aircraft;

    INSERT INTO staging.aircraft (
        icao24, registration, manufacturer_icao, manufacturer_name, model, typecode,
        icao_aircraft_class, category_description, country, operator, operator_icao,
        owner, load_id
    )
    SELECT
        lower(trim(c.icao24)),
        NULLIF(trim(c.registration), ''),
        NULLIF(trim(c.manufacturericao), ''),
        NULLIF(trim(c.manufacturername), ''),
        NULLIF(trim(c.model), ''),
        NULLIF(trim(c.typecode), ''),
        NULLIF(trim(c.icaoaircraftclass), ''),
        NULLIF(trim(c.categorydescription), ''),
        NULLIF(trim(c.country), ''),
        NULLIF(trim(c.operator), ''),
        NULLIF(trim(c.operatoricao), ''),
        NULLIF(trim(c.owner), ''),
        c.load_id
    FROM raw.aircraft_catalog c
    WHERE c.load_id = v_load
      AND lower(trim(c.icao24)) ~ '^[0-9a-f]{6}$'
    ON CONFLICT (icao24) DO NOTHING;
    GET DIAGNOSTICS v_kept = ROW_COUNT;

    SELECT count(*) INTO v_total FROM raw.aircraft_catalog c WHERE c.load_id = v_load;

    RETURN QUERY SELECT v_load, v_total, v_kept, v_total - v_kept;
END;
$$;
