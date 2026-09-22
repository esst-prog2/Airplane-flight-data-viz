CREATE TABLE IF NOT EXISTS staging.state_position (
    id                     bigserial PRIMARY KEY,
    source_raw_id          bigint NOT NULL REFERENCES raw.state_snapshot (id),
    icao24                 text NOT NULL,
    callsign               text,
    time_position           timestamptz NOT NULL,
    latitude               double precision NOT NULL,
    longitude              double precision NOT NULL,
    baro_altitude          double precision,
    on_ground              boolean,
    altitude_missing       boolean NOT NULL DEFAULT false,
    altitude_implausible   boolean NOT NULL DEFAULT false,
    callsign_missing       boolean NOT NULL DEFAULT false,
    position_stale         boolean NOT NULL DEFAULT false,
    inserted_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (icao24, time_position)
);

CREATE INDEX IF NOT EXISTS ix_state_position_source_raw_id
    ON staging.state_position (source_raw_id);

CREATE TABLE IF NOT EXISTS staging.rejects (
    id              bigserial PRIMARY KEY,
    source_raw_id   bigint NOT NULL REFERENCES raw.state_snapshot (id),
    reason          text NOT NULL CHECK (reason IN (
        'missing_icao24',
        'missing_position',
        'missing_time_position',
        'impossible_coordinate'
    )),
    rejected_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_rejects_source_raw_id
    ON staging.rejects (source_raw_id);
