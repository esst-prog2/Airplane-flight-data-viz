-- flights_ro: a least-privilege, read-only role for the dashboard, its API, and
-- any metrics / monitoring reader. It holds only CONNECT + USAGE + SELECT and is
-- never granted a write (see the mart-read-api and dashboard-distribution specs).
--
-- The login password is set out of band on deploy and is never stored in the
-- repository: on the VPS the user runs, once,
--     ALTER ROLE flights_ro WITH LOGIN PASSWORD '...';   -- value from .env
-- so the API can connect over TCP. The role is created NOLOGIN here; locally it
-- is verified with SET ROLE (no login needed) that it can SELECT but not write.
--
-- Not loaded by the test harness (it lives under sql/roles/, which conftest does
-- not apply) because a role is a cluster-global object and GRANT CONNECT names
-- the 'flights' database, neither of which fits the throwaway per-test databases.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'flights_ro') THEN
        CREATE ROLE flights_ro NOLOGIN;
    END IF;
END $$;

GRANT CONNECT ON DATABASE flights TO flights_ro;
GRANT USAGE  ON SCHEMA mart TO flights_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA mart TO flights_ro;

-- future mart tables are readable too, without re-granting
ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT SELECT ON TABLES TO flights_ro;
