CREATE TABLE IF NOT EXISTS raw.state_snapshot (
    id          bigserial PRIMARY KEY,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    api_time    bigint      NOT NULL,
    payload     jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_state_snapshot_api_time
    ON raw.state_snapshot (api_time);