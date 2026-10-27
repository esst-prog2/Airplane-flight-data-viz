-- mart.dim_aircraft: one row per airframe (icao24) plus an unknown member (sk 0).
-- SCD Type 1. The surrogate key is assigned once per icao24 and never changes, so
-- the table is loaded by UPSERT (never truncated) even though staging.aircraft is
-- rebuilt from scratch on each catalogue load (DESIGN.md 5.1, PLANNING_LOG 2026-10-21/27).
-- No manufacturer, no built_year, no engines (measured near-empty for this traffic).
-- owner is stored but NEVER displayed on the dashboard.

CREATE SEQUENCE IF NOT EXISTS mart.dim_aircraft_sk_seq START 1;

CREATE TABLE IF NOT EXISTS mart.dim_aircraft (
    aircraft_sk          BIGINT PRIMARY KEY,               -- 0 = unknown member
    icao24               CHAR(6) UNIQUE,                   -- NULL only for unknown member
    -- Lengths widened from DESIGN.md after measuring the real catalogue: typecode and
    -- operator_icao are not always clean codes (some hold full type/company names,
    -- max 26 / 32 chars in the 2025-08 catalogue), so these are not short code fields.
    registration         VARCHAR(32)  NOT NULL,
    type_designator      VARCHAR(40)  NOT NULL,
    model                VARCHAR(200) NOT NULL,
    aircraft_category    VARCHAR(100) NOT NULL,
    operator             VARCHAR(200) NOT NULL,
    operator_icao        VARCHAR(40)  NOT NULL,
    owner                VARCHAR(200) NOT NULL,
    registration_country VARCHAR(100) NOT NULL,
    in_catalog           BOOLEAN      NOT NULL,
    loaded_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CHECK ((aircraft_sk = 0) = (NOT in_catalog)),
    CHECK ((aircraft_sk = 0) = (icao24 IS NULL))
);

-- Inserts the unknown member if missing, then upserts every staging.aircraft row by
-- icao24: a new icao24 gets a fresh sk from the sequence; an existing one keeps its sk
-- and has its attributes overwritten. Never truncates. Text attributes are never NULL
-- (sentinel 'Unknown'). Safe to re-run after a catalogue reload.
CREATE OR REPLACE FUNCTION mart.load_dim_aircraft()
RETURNS TABLE (inserted bigint, updated bigint) LANGUAGE plpgsql AS $$
DECLARE
    v_before bigint;
    v_after  bigint;
    v_upd    bigint;
BEGIN
    INSERT INTO mart.dim_aircraft (
        aircraft_sk, icao24, registration, type_designator, model, aircraft_category,
        operator, operator_icao, owner, registration_country, in_catalog
    )
    VALUES (0, NULL, 'Unknown', 'Unknown', 'Unknown', 'Unknown',
            'Unknown', 'Unknown', 'Unknown', 'Unknown', FALSE)
    ON CONFLICT (aircraft_sk) DO NOTHING;

    SELECT count(*) INTO v_before FROM mart.dim_aircraft;

    INSERT INTO mart.dim_aircraft (
        aircraft_sk, icao24, registration, type_designator, model, aircraft_category,
        operator, operator_icao, owner, registration_country, in_catalog
    )
    SELECT
        nextval('mart.dim_aircraft_sk_seq'),
        a.icao24,
        coalesce(a.registration, 'Unknown'),
        coalesce(a.typecode, 'Unknown'),
        coalesce(a.model, 'Unknown'),
        coalesce(a.category_description, 'Unknown'),
        coalesce(a.operator, 'Unknown'),
        coalesce(a.operator_icao, 'Unknown'),
        coalesce(a.owner, 'Unknown'),
        coalesce(a.country, 'Unknown'),
        TRUE
    FROM staging.aircraft a
    ON CONFLICT (icao24) DO UPDATE SET
        registration         = EXCLUDED.registration,
        type_designator      = EXCLUDED.type_designator,
        model                = EXCLUDED.model,
        aircraft_category    = EXCLUDED.aircraft_category,
        operator             = EXCLUDED.operator,
        operator_icao        = EXCLUDED.operator_icao,
        owner                = EXCLUDED.owner,
        registration_country = EXCLUDED.registration_country,
        in_catalog           = TRUE,
        loaded_at            = now();
    GET DIAGNOSTICS v_upd = ROW_COUNT;

    SELECT count(*) INTO v_after FROM mart.dim_aircraft;

    inserted := v_after - v_before;
    updated  := v_upd - inserted;   -- rows touched minus the ones that were new
    RETURN NEXT;
END;
$$;
