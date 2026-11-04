-- Thread memory for ty-agent (spec §6.4.5, Milestone 5).
create schema if not exists agent;
create table if not exists agent.threads (
  thread_id  text primary key,
  user_id    uuid references auth.users on delete cascade,   -- null = anonymous public thread
  created_at timestamptz not null default now(),
  last_seen  timestamptz not null default now()
);
create index if not exists threads_last_seen on agent.threads (last_seen);
-- LangGraph's checkpoint tables are created in this schema by AsyncPostgresSaver.setup()
revoke all on schema agent from anon, authenticated, public;   -- never exposed through the Data API

do $$ begin
  if exists (select from pg_roles where rolname = 'ty_agent') then
    grant usage, create on schema agent to ty_agent;
    grant select, insert, update, delete on all tables in schema agent to ty_agent;
    alter default privileges in schema agent grant select, insert, update, delete on tables to ty_agent;
  end if;
  if exists (select from pg_roles where rolname = 'ty_worker') then
    grant usage on schema agent to ty_worker;                    -- nightly 30-day purge only
    grant select, delete on all tables in schema agent to ty_worker;
    alter default privileges in schema agent grant select, delete on tables to ty_worker;
  end if;
end $$;
