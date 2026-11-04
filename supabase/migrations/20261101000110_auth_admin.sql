-- Milestone 9: role claim, audit chain, answers, kill switches, officer warning areas, account deletion, retention.
-- (spec §8.3–8.5, §9.1, §9.5, §10.3)

-- ── role claim (Supabase custom access token hook) ──────────────────────────────────────────────
-- Enable once in the dashboard: Authentication → Hooks → Customize Access Token → public.custom_access_token_hook
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb language plpgsql stable as $$
declare r public.app_role;
begin
  select role into r from public.user_roles where user_id = (event->>'user_id')::uuid;
  return jsonb_set(event, '{claims,app_role}', to_jsonb(coalesce(r, 'fisher'::public.app_role)));
end $$;
grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook from authenticated, anon, public;
grant select on public.user_roles to supabase_auth_admin;
do $$ begin
  create policy user_roles_auth_admin on public.user_roles as permissive for select to supabase_auth_admin using (true);
exception when duplicate_object then null; end $$;

-- staff checks used by policies: role from the JWT claim, MFA level aal2
create or replace function public.is_staff(roles text[]) returns boolean language sql stable as $$
  select coalesce(auth.jwt()->>'app_role', '') = any(roles) and coalesce(auth.jwt()->>'aal', '') = 'aal2'
$$;

-- ── tamper-evident audit log (append-only; each row hashes the previous one) ──────────────────────
create table if not exists public.audit_log (
  id bigint generated always as identity primary key,
  actor uuid, action text not null, target text, detail jsonb,
  at timestamptz not null default now(),
  prev_hash char(64), row_hash char(64) not null default ''
);
create or replace function public.audit_hash(prev char(64), actor uuid, action text, target text, detail jsonb,
                                            at timestamptz) returns char(64)
language sql immutable as $$
  select encode(extensions.digest(concat_ws('|', prev, actor::text, action, target, detail::text,
                to_char(at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US')), 'sha256'), 'hex')
$$;
create or replace function public.audit_chain() returns trigger language plpgsql as $$
declare last char(64);
begin
  perform pg_advisory_xact_lock(4242);
  select row_hash into last from public.audit_log order by id desc limit 1;
  new.prev_hash := coalesce(last, repeat('0', 64));
  new.row_hash := public.audit_hash(new.prev_hash, new.actor, new.action, new.target, new.detail, new.at);
  return new;
end $$;
drop trigger if exists audit_chain on public.audit_log;
create trigger audit_chain before insert on public.audit_log for each row execute function public.audit_chain();
alter table public.audit_log enable row level security;
revoke update, delete, truncate on public.audit_log from public, anon, authenticated;
grant select on public.audit_log to authenticated;
do $$ begin
  create policy audit_admin_read on public.audit_log for select to authenticated
    using (public.is_staff(array['platform_admin']));
exception when duplicate_object then null; end $$;

-- recompute every hash; returns the first broken row id (null = chain intact)
create or replace function public.audit_verify() returns bigint
language plpgsql stable security definer set search_path = '' as $$
declare r record; prev char(64) := repeat('0', 64);
begin
  if not public.is_staff(array['platform_admin']) and current_user not in ('ty_worker', 'postgres') then
    raise exception 'platform_admin with MFA only' using errcode = '42501';
  end if;
  for r in select * from public.audit_log order by id loop
    if r.prev_hash <> prev or r.row_hash <> public.audit_hash(r.prev_hash, r.actor, r.action, r.target, r.detail, r.at) then
      return r.id;
    end if;
    prev := r.row_hash;
  end loop;
  return null;
end $$;
grant execute on function public.audit_verify() to authenticated;

-- a user's own events (consent, data export, deletion, sharing) — written as that user
create or replace function public.audit(p_action text, p_target text, p_detail jsonb)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'login required' using errcode = '42501'; end if;
  if p_action not in ('consent.given', 'consent.withdrawn', 'data.exported', 'account.delete_requested',
                      'account.delete_cancelled', 'share.created', 'share.revoked', 'push.subscribed') then
    raise exception 'unknown audit action %', p_action using errcode = '22023';
  end if;
  insert into public.audit_log (actor, action, target, detail) values (auth.uid(), p_action, p_target, p_detail);
end $$;
revoke all on function public.audit(text, text, jsonb) from public, anon;
grant execute on function public.audit(text, text, jsonb) to authenticated;

-- ── answers: every reply with the exact model, prompt and config that produced it (180 days) ─────
create table if not exists public.answers (
  id uuid primary key default gen_random_uuid(),
  thread_id text not null,
  user_id uuid references auth.users(id) on delete cascade,   -- null = anonymous
  created_at timestamptz not null default now(),
  lang text not null,
  mode text not null check (mode in ('simple', 'expert')),
  question text check (length(question) <= 2000),
  reply text,
  verdict text check (verdict in ('GO', 'CAUTION', 'NO-GO')),
  ledger_answer_id text,                                      -- Neo4j (:Answer {id})
  citations jsonb not null default '[]',
  guard jsonb not null default '{}',
  fallback text,
  model text not null,
  prompt_version text not null,
  config_version text not null
);
create index if not exists answers_user_time on public.answers (user_id, created_at desc);
create index if not exists answers_guard on public.answers (created_at desc)
  where (guard->>'ungrounded_number')::int > 0 or (guard->>'quote_dropped')::int > 0
        or (guard->>'template_fallback')::boolean or (guard->>'language_mismatch')::boolean;
alter table public.answers enable row level security;
grant select on public.answers to authenticated;
do $$ begin
  create policy answers_owner on public.answers for select to authenticated using (user_id = auth.uid());
  create policy answers_staff on public.answers for select to authenticated
    using (public.is_staff(array['platform_admin', 'analyst']));
exception when duplicate_object then null; end $$;
do $$ begin
  if exists (select from pg_roles where rolname = 'ty_agent') then
    grant usage on schema public to ty_agent;
    grant insert on public.answers to ty_agent;
    grant select on public.flags to ty_agent;
  end if;
exception when undefined_table then null; end $$;

-- ── kill switches (spec §9.5): free-form chat off; alerts paused for a region ─────────────────────
create table if not exists public.flags (
  key text primary key check (key in ('free_chat_off', 'alerts_paused')),
  value jsonb not null,
  reason text not null check (length(reason) between 3 and 500),
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now()
);
insert into public.flags (key, value, reason) values
  ('free_chat_off', 'false', 'initial'), ('alerts_paused', '[]', 'initial')
on conflict (key) do nothing;
alter table public.flags enable row level security;
grant select on public.flags to anon, authenticated;
do $$ begin
  create policy flags_read on public.flags for select to anon, authenticated using (true);
exception when duplicate_object then null; end $$;
do $$ begin
  if exists (select from pg_roles where rolname = 'ty_agent') then grant select on public.flags to ty_agent; end if;
end $$;

-- every switch change is audit-logged with its reason; only an admin with MFA may flip one
create or replace function public.set_flag(p_key text, p_value jsonb, p_reason text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_staff(array['platform_admin']) then
    raise exception 'platform_admin with MFA only' using errcode = '42501';
  end if;
  update public.flags set value = p_value, reason = p_reason, updated_by = auth.uid(), updated_at = now()
   where key = p_key;
  if not found then raise exception 'unknown flag %', p_key using errcode = '22023'; end if;
  insert into public.audit_log (actor, action, target, detail)
  values (auth.uid(), 'flag.set', p_key, jsonb_build_object('value', p_value, 'reason', p_reason));
end $$;
revoke all on function public.set_flag(text, jsonb, text) from public, anon;
grant execute on function public.set_flag(text, jsonb, text) to authenticated;

-- staff set roles (invite analyst / officer / admin; suspend = back to fisher), audit-logged
create or replace function public.set_role(p_user uuid, p_role public.app_role, p_reason text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_staff(array['platform_admin']) then
    raise exception 'platform_admin with MFA only' using errcode = '42501';
  end if;
  insert into public.user_roles (user_id, role) values (p_user, p_role)
  on conflict (user_id) do update set role = excluded.role;
  insert into public.audit_log (actor, action, target, detail)
  values (auth.uid(), 'role.set', p_user::text, jsonb_build_object('role', p_role, 'reason', p_reason));
end $$;
revoke all on function public.set_role(uuid, public.app_role, text) from public, anon;
grant execute on function public.set_role(uuid, public.app_role, text) to authenticated;

-- ── officer view: positions only inside active official warning areas, last hour, MFA ─────────────
create table if not exists public.warning_areas (
  id text primary key,
  issuer text not null,
  title text not null,
  geom extensions.geography(MultiPolygon, 4326) not null,
  valid_from timestamptz not null,
  valid_to timestamptz not null,
  updated_at timestamptz not null default now()
);
create index if not exists warning_areas_geom on public.warning_areas using gist (geom);
alter table public.warning_areas enable row level security;
grant select on public.warning_areas to anon, authenticated;
do $$ begin
  create policy warning_areas_read on public.warning_areas for select to anon, authenticated using (true);
exception when duplicate_object then null; end $$;
create or replace view public.active_warning_areas with (security_invoker = true) as
  select * from public.warning_areas where valid_from <= now() and valid_to > now();
grant select on public.active_warning_areas to anon, authenticated;

drop policy if exists positions_officer on public.positions;
create policy positions_officer on public.positions for select to authenticated
  using (public.is_staff(array['officer']) and recorded_at > now() - interval '1 hour'
         and exists (select 1 from public.active_warning_areas w where extensions.st_intersects(w.geom, positions.geom)));

-- ── account deletion: 7-day undo, then the worker deletes the auth user (everything cascades) ────
create table if not exists public.deletion_requests (
  user_id uuid primary key references auth.users(id) on delete cascade,
  requested_at timestamptz not null default now(),
  delete_after timestamptz not null default now() + interval '7 days'
);
alter table public.deletion_requests enable row level security;
grant select, insert, delete on public.deletion_requests to authenticated;
do $$ begin
  create policy deletion_owner on public.deletion_requests for all to authenticated
    using (user_id = auth.uid()) with check (user_id = auth.uid());
exception when duplicate_object then null; end $$;

-- ── retention aggregate: positions older than 30 days become H3-cell counts with no user id ──────
create table if not exists public.position_cells (
  day date not null, cell text not null, fixes int not null, primary key (day, cell)
);
alter table public.position_cells enable row level security;
grant select on public.position_cells to authenticated;
do $$ begin
  create policy position_cells_staff on public.position_cells for select to authenticated
    using (public.is_staff(array['platform_admin', 'analyst', 'officer']));
exception when duplicate_object then null; end $$;

-- the worker (retention, deletion, warning areas, admin reads) needs these beyond its defaults
do $$ begin
  if exists (select from pg_roles where rolname = 'ty_worker') then
    grant select, insert, update on all tables in schema public to ty_worker;
    grant delete on public.positions, public.answers, public.deletion_requests, public.warning_areas to ty_worker;
    grant usage, select on all sequences in schema public to ty_worker;
  end if;
end $$;
