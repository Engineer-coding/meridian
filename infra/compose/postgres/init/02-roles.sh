#!/bin/sh
# Uygulama rolleri (ADR-0002): tablo sahibi ve çalışma zamanı rolü ayrıdır.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
CREATE ROLE meridian_owner LOGIN PASSWORD '${DB_OWNER_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE meridian_app   LOGIN PASSWORD '${DB_APP_PASSWORD}'   NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

CREATE SCHEMA core AUTHORIZATION meridian_owner;
GRANT USAGE ON SCHEMA core TO meridian_app;

ALTER DEFAULT PRIVILEGES FOR ROLE meridian_owner IN SCHEMA core
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO meridian_app;
ALTER DEFAULT PRIVILEGES FOR ROLE meridian_owner IN SCHEMA core
    GRANT USAGE, SELECT ON SEQUENCES TO meridian_app;

ALTER ROLE meridian_owner SET search_path = core, public;
ALTER ROLE meridian_app   SET search_path = core, public;
EOSQL