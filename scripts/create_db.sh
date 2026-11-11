#!/usr/bin/env bash
# Create the local role + databases (requires a superuser connection via psql defaults).
set -euo pipefail
psql -d postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='ledgerflow'" | grep -q 1 || \
  psql -d postgres -c "CREATE ROLE ledgerflow LOGIN PASSWORD 'ledgerflow' CREATEDB;"
for db in ledgerflow ledgerflow_test; do
  psql -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 || \
    psql -d postgres -c "CREATE DATABASE $db OWNER ledgerflow;"
done
echo "databases ready"
