#!/usr/bin/env bash
# Create the service login roles (spec §13.10). Run after migrations, against SUPABASE_DB_URL (admin).
# Usage: API_PW=… WORKER_PW=… AGENT_PW=… scripts/db_roles.sh
# Then put the same passwords into DATABASE_URL / WORKER_DATABASE_URL / AGENT_DATABASE_URL in .env.
set -euo pipefail
: "${SUPABASE_DB_URL:?set SUPABASE_DB_URL (admin connection)}"
: "${API_PW:?}" "${WORKER_PW:?}" "${AGENT_PW:?}"

psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 \
  -v api_pw="$API_PW" -v worker_pw="$WORKER_PW" -v agent_pw="$AGENT_PW" <<'SQL'
do $$ begin
  if not exists (select from pg_roles where rolname = 'ty_api') then
    create role ty_api login noinherit;            -- no BYPASSRLS
  end if;
  if not exists (select from pg_roles where rolname = 'ty_worker') then
    create role ty_worker login bypassrls;         -- alerts across boats, kb writes; never web-reachable
  end if;
  if not exists (select from pg_roles where rolname = 'ty_agent') then
    create role ty_agent login noinherit;          -- schema `agent` only (spec §6.4.5)
  end if;
end $$;
alter role ty_api password :'api_pw';
alter role ty_worker password :'worker_pw';
alter role ty_agent password :'agent_pw';
grant authenticated to ty_api;                     -- may SET ROLE authenticated
grant usage on schema public to ty_worker;
grant select, insert, update on all tables in schema public to ty_worker;
-- revoke update, delete on audit_log from ty_worker;   -- Milestone 9 (table created then)
SQL
echo "roles ready: ty_api, ty_worker, ty_agent"
