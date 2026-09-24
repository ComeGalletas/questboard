#!/bin/sh
# Starts the local Supabase stack (Docker), makes sure the single test user exists, and runs the
# runner's live integration tests against it. Safe to re-run; `pnpm db:reset` wipes the data.
#
#   supabase/tests/live.sh
set -eu
repo="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo"
export SUPABASE_TELEMETRY_DISABLED=1
services_off="studio,imgproxy,edge-runtime,logflare,vector,supavisor,mailpit,postgres-meta,storage-api"

pnpm exec supabase status >/dev/null 2>&1 || pnpm exec supabase start -x "$services_off"
status="$(pnpm exec supabase status -o json 2>/dev/null)"
field() { printf '%s' "$status" | python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }

export QUESTBOARD_IT_URL="$(field API_URL)"
export QUESTBOARD_IT_ANON_KEY="$(field ANON_KEY)"
export QUESTBOARD_IT_EMAIL="${QUESTBOARD_IT_EMAIL:-me@questboard.test}"
export QUESTBOARD_IT_PASSWORD="${QUESTBOARD_IT_PASSWORD:-quest-pass-123}"
service_key="$(field SERVICE_ROLE_KEY)"

# Sign-ups are off, so the one user is created with the local admin API. A second attempt
# (or any other address) is refused by the single-user trigger; that's fine here.
curl -s --noproxy '*' -o /dev/null -X POST "$QUESTBOARD_IT_URL/auth/v1/admin/users" \
  -H "apikey: $service_key" -H "Authorization: Bearer $service_key" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$QUESTBOARD_IT_EMAIL\",\"password\":\"$QUESTBOARD_IT_PASSWORD\",\"email_confirm\":true}" \
  || true

cd runner && uv run pytest -q tests/integration
