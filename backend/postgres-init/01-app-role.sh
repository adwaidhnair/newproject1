#!/bin/sh
set -eu

psql \
  --host "${PGHOST:-db}" \
  --port "${PGPORT:-5432}" \
  --username "${PGUSER:-erp_intel}" \
  --dbname "${PGDATABASE:-erp_intel}" \
  --set=ON_ERROR_STOP=1 \
  --set=app_db_password="$APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE erp_intel_app LOGIN PASSWORD %L', :'app_db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'erp_intel_app')
\gexec

ALTER ROLE erp_intel_app PASSWORD :'app_db_password';
GRANT CONNECT ON DATABASE erp_intel TO erp_intel_app;
GRANT USAGE ON SCHEMA public TO erp_intel_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO erp_intel_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO erp_intel_app;
ALTER DEFAULT PRIVILEGES FOR ROLE erp_intel IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO erp_intel_app;
ALTER DEFAULT PRIVILEGES FOR ROLE erp_intel IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO erp_intel_app;
SQL
