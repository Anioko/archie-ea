#!/bin/bash
# Postgres entrypoint init script (runs once, on first container start).
# Creates the dev and test databases the app expects. The POSTGRES_DB created
# by the image ("postgres") stays as the maintenance database.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE archie'
      WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'archie')\gexec
    SELECT 'CREATE DATABASE archie_test'
      WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'archie_test')\gexec
EOSQL

echo "init-databases.sh: ensured databases 'archie' and 'archie_test' exist"
