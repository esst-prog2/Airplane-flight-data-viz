-- mart.dim_region: the collection bounding box as one current row, SCD2 structure
-- kept for a possible future region (never exercised now). The bbox bounds are the
-- BBOX constants in ingest.py (lamin 45.0, lomin 12.0, lamax 50.0, lomax 23.0),
-- verified against the frozen file on 2026-10-27; a test checks they still match.

CREATE TABLE IF NOT EXISTS mart.dim_region (
    region_sk          INTEGER PRIMARY KEY,
    region_code        VARCHAR(20)  NOT NULL,
    region_name_en     VARCHAR(100) NOT NULL,
    region_name_hu     VARCHAR(100) NOT NULL,
    bbox_min_latitude  NUMERIC(9,6) NOT NULL,
    bbox_max_latitude  NUMERIC(9,6) NOT NULL,
    bbox_min_longitude NUMERIC(9,6) NOT NULL,
    bbox_max_longitude NUMERIC(9,6) NOT NULL,
    bbox_area_km2      INTEGER      NOT NULL,
    valid_from         TIMESTAMPTZ  NOT NULL,
    valid_to           TIMESTAMPTZ,
    is_current         BOOLEAN      NOT NULL,
    UNIQUE (region_code, valid_from),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    CHECK ((valid_to IS NULL) = is_current)
);

-- Inserts the single current region row if it is not there yet. valid_from is the
-- start of collection (min fetched_at in raw). bbox_area_km2 is the spherical
-- zone-sector area: R^2 * radians(dlon) * (sin(lat_max) - sin(lat_min)).
CREATE OR REPLACE FUNCTION mart.load_dim_region()
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_count       bigint;
    v_min_lat     numeric := 45.0;
    v_min_lon     numeric := 12.0;
    v_max_lat     numeric := 50.0;
    v_max_lon     numeric := 23.0;
    v_valid_from  timestamptz;
    v_area        int;
BEGIN
    SELECT min(fetched_at) INTO v_valid_from FROM raw.state_snapshot;
    IF v_valid_from IS NULL THEN
        RAISE EXCEPTION 'raw.state_snapshot is empty: cannot set region valid_from';
    END IF;

    v_area := round(
        6371.0 * 6371.0
        * radians(v_max_lon - v_min_lon)
        * (sin(radians(v_max_lat)) - sin(radians(v_min_lat)))
    )::int;

    INSERT INTO mart.dim_region (
        region_sk, region_code, region_name_en, region_name_hu,
        bbox_min_latitude, bbox_max_latitude, bbox_min_longitude, bbox_max_longitude,
        bbox_area_km2, valid_from, valid_to, is_current
    )
    VALUES (
        1, 'CEU', 'Central Europe', 'Közép-Európa',
        v_min_lat, v_max_lat, v_min_lon, v_max_lon,
        v_area, v_valid_from, NULL, TRUE
    )
    ON CONFLICT (region_code, valid_from) DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;
