-- OpenSky aircraft catalogue: icao24 -> type, manufacturer, operator, country.
-- Same two-step pattern as the flight data: land the file untouched, clean it
-- in a separate step (staging.build_aircraft(), sql/transform/aircraft_build.sql).
--
-- One row per loaded file in raw.aircraft_catalog_load (identified by the
-- SHA-256 of the file, so the same file is never loaded twice), and the 32
-- source columns as text in raw.aircraft_catalog, tagged with that load.

CREATE TABLE IF NOT EXISTS raw.aircraft_catalog_load (
    id             bigserial PRIMARY KEY,
    source_file    text        NOT NULL,
    source_sha256  text        NOT NULL UNIQUE,
    row_count      bigint      NOT NULL,
    loaded_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.aircraft_catalog (
    load_id             bigint NOT NULL REFERENCES raw.aircraft_catalog_load (id),
    icao24              text,
    source_timestamp    text,
    acars               text,
    adsb                text,
    built               text,
    categorydescription text,
    country             text,
    engines             text,
    firstflightdate     text,
    firstseen           text,
    icaoaircraftclass   text,
    linenumber          text,
    manufacturericao    text,
    manufacturername    text,
    model               text,
    modes               text,
    nextreg             text,
    notes               text,
    operator            text,
    operatorcallsign    text,
    operatoriata        text,
    operatoricao        text,
    owner               text,
    prevreg             text,
    reguntil            text,
    registered          text,
    registration        text,
    selcal              text,
    serialnumber        text,
    status              text,
    typecode            text,
    vdl                 text
);

CREATE INDEX IF NOT EXISTS ix_aircraft_catalog_load_id
    ON raw.aircraft_catalog (load_id);

-- Cleaned catalogue: one row per valid icao24, rebuilt from the latest load.
CREATE TABLE IF NOT EXISTS staging.aircraft (
    icao24               text PRIMARY KEY CHECK (icao24 ~ '^[0-9a-f]{6}$'),
    registration         text,
    manufacturer_icao    text,
    manufacturer_name    text,
    model                text,
    typecode             text,
    icao_aircraft_class  text,
    category_description text,
    country              text,
    operator             text,
    operator_icao        text,
    owner                text,
    load_id              bigint NOT NULL REFERENCES raw.aircraft_catalog_load (id)
);
