#!/bin/sh
# Applies the Supabase migrations to a throwaway local Postgres (with a small Supabase shim)
# and runs the assertions + schema drift check. Needs Postgres 15+ server binaries and uv.
#
#   supabase/tests/run.sh             # PG_BIN overrides the server binary directory
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
bin="${PG_BIN:-$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1)}"

tmp="$(mktemp -d)"
as_pg=""
if [ "$(id -u)" = 0 ]; then  # initdb refuses to run as root (e.g. in containers)
  as_pg="runuser -u postgres --"
  chown postgres "$tmp"
fi
cleanup() { $as_pg "$bin/pg_ctl" -D "$tmp/data" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$tmp"; }
trap cleanup EXIT

$as_pg "$bin/initdb" -D "$tmp/data" -U postgres -A trust --no-sync >/dev/null
$as_pg "$bin/pg_ctl" -D "$tmp/data" -o "-k $tmp -c listen_addresses='' -c wal_level=logical" -l "$tmp/log" -w start >/dev/null

export PGHOST="$tmp" PGUSER=postgres PGDATABASE=postgres
run_sql() { psql -X -q -v ON_ERROR_STOP=1 -o /dev/null -f "$1"; }

run_sql "$here/shim.sql"
for migration in "$repo"/supabase/migrations/*.sql; do
  run_sql "$migration"
done
run_sql "$here/assertions.sql"
(cd "$repo/runner" && uv run --quiet python "$here/check_schema.py")
