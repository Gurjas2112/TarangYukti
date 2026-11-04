-- Core personal tables (spec §8.3, §8.4, §9.1.2) — Milestone 6: onboarding, boats, prefs, consents, push.
-- Every table has RLS: owner-only by default; family reads a boat only with an unexpired grant.
-- The roles hook, audit log and officer policies arrive in Milestone 9; positions/trips are used from Milestone 8.

create extension if not exists pgcrypto with schema extensions;

do $$ begin
  create type public.app_role as enum ('fisher','family','analyst','officer','platform_admin');
exception when duplicate_object then null; end $$;

create table if not exists public.user_roles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role public.app_role not null default 'fisher'
);

create table if not exists public.boats (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (length(name) between 1 and 60),
  kind text not null check (kind in ('non_motorised','small_frp','mechanised_trawler')),
  registration_no text check (registration_no ~ '^[A-Z0-9-]{4,20}$'),
  home_harbour text,
  created_at timestamptz not null default now()
);
create index if not exists boats_owner on public.boats (owner_id);

create table if not exists public.positions (
  id bigint generated always as identity primary key,
  boat_id uuid not null references public.boats(id) on delete cascade,
  geom extensions.geography(Point, 4326) not null,
  speed_knots real check (speed_knots between 0 and 40),
  recorded_at timestamptz not null,
  source text not null check (source in ('web_live','mobile_app','simulated'))
);
create index if not exists positions_geom on public.positions using gist (geom);
create index if not exists positions_time on public.positions using brin (recorded_at);

create table if not exists public.push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  kind text not null default 'web' check (kind in ('web','expo')),
  endpoint text not null unique,                   -- web: push service URL; expo: ExponentPushToken[…]
  p256dh text,
  auth text,
  check ((kind = 'web' and endpoint like 'https://%' and p256dh is not null and auth is not null)
         or (kind = 'expo' and endpoint like 'ExponentPushToken[%')),
  user_agent text,
  created_at timestamptz not null default now(),
  last_ok_at timestamptz
);
create index if not exists push_subscriptions_user on public.push_subscriptions (user_id);

create table if not exists public.share_grants (
  id uuid primary key default gen_random_uuid(),
  boat_id uuid not null references public.boats(id) on delete cascade,
  grantee_email text not null,
  grantee_id uuid references auth.users(id),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (expires_at > created_at)
);

create table if not exists public.user_prefs (
  user_id uuid primary key references auth.users(id) on delete cascade,
  mode text not null default 'simple' check (mode in ('simple','expert')),
  language text,                                   -- BCP-47 of a released language; null = device locale
  home_harbour text,                               -- config/harbours.yaml id
  brief_time time,                                 -- null = learned from trips, default 04:00 IST
  quiet_from time not null default '21:00', quiet_to time not null default '03:30'
);

create table if not exists public.trips (
  id uuid primary key default gen_random_uuid(),
  boat_id uuid not null references public.boats(id) on delete cascade,
  departed_at timestamptz not null,
  returned_at timestamptz check (returned_at is null or returned_at > departed_at),
  closed_by text check (closed_by in ('geofence','button')),
  advice_answer_id uuid,
  advice_verdict text check (advice_verdict in ('GO','CAUTION','NO-GO')),
  feedback text check (feedback in ('right','wrong')),
  feedback_note text check (length(feedback_note) <= 500)
);
create index if not exists trips_boat on public.trips (boat_id, departed_at desc);

create table if not exists public.consents (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  purpose text not null check (purpose in ('location_alerts','family_sharing','voice_processing')),
  notice_version text not null,
  language text not null,
  given_at timestamptz not null default now(),
  withdrawn_at timestamptz
);
create index if not exists consents_user on public.consents (user_id);

-- Every push the worker sends (briefs, alerts, tests): alert budget, de-duplication and retries read it.
-- Holds short text only — never coordinates.
create table if not exists public.alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  boat_id uuid references public.boats(id) on delete cascade,
  kind text not null check (kind in ('brief','alert','family','test')),
  rule text,                                       -- e.g. H1, border-5km, brief
  critical boolean not null default false,
  title text not null check (length(title) <= 120),
  body text not null check (length(body) <= 500),
  lang text not null,
  answer_id uuid,
  status text not null default 'pending' check (status in ('pending','sent','failed','suppressed')),
  attempts int not null default 0,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
create index if not exists alerts_user_time on public.alerts (user_id, created_at desc);

-- ── Row-level security (spec §8.4)
alter table public.user_roles enable row level security;
alter table public.boats enable row level security;
alter table public.positions enable row level security;
alter table public.push_subscriptions enable row level security;
alter table public.share_grants enable row level security;
alter table public.user_prefs enable row level security;
alter table public.trips enable row level security;
alter table public.consents enable row level security;
alter table public.alerts enable row level security;

do $$ begin
  -- a user may read their role and claim only the self-service roles; staff roles are granted by an admin
  create policy user_roles_read on public.user_roles for select to authenticated using (user_id = auth.uid());
  create policy user_roles_self on public.user_roles for insert to authenticated
    with check (user_id = auth.uid() and role in ('fisher','family'));

  create policy boats_owner on public.boats for all to authenticated
    using (owner_id = auth.uid()) with check (owner_id = auth.uid());
  create policy boats_family on public.boats for select to authenticated
    using (exists (select 1 from public.share_grants g where g.boat_id = boats.id and g.grantee_id = auth.uid()
                   and g.revoked_at is null and g.expires_at > now()));

  create policy positions_owner_or_family on public.positions for select to authenticated
    using (exists (select 1 from public.boats b where b.id = positions.boat_id));
  create policy positions_owner_insert on public.positions for insert to authenticated
    with check (exists (select 1 from public.boats b where b.id = positions.boat_id and b.owner_id = auth.uid()));

  create policy push_owner on public.push_subscriptions for all to authenticated
    using (user_id = auth.uid()) with check (user_id = auth.uid());

  create policy grants_owner on public.share_grants for all to authenticated
    using (exists (select 1 from public.boats b where b.id = share_grants.boat_id and b.owner_id = auth.uid()))
    with check (exists (select 1 from public.boats b where b.id = share_grants.boat_id and b.owner_id = auth.uid()));
  create policy grants_grantee on public.share_grants for select to authenticated using (grantee_id = auth.uid());

  create policy prefs_owner on public.user_prefs for all to authenticated
    using (user_id = auth.uid()) with check (user_id = auth.uid());

  create policy trips_owner_or_family on public.trips for select to authenticated
    using (exists (select 1 from public.boats b where b.id = trips.boat_id));
  create policy trips_owner_write on public.trips for all to authenticated
    using (exists (select 1 from public.boats b where b.id = trips.boat_id and b.owner_id = auth.uid()))
    with check (exists (select 1 from public.boats b where b.id = trips.boat_id and b.owner_id = auth.uid()));

  -- consents are append-only for the user (withdrawal = update of withdrawn_at)
  create policy consents_read on public.consents for select to authenticated using (user_id = auth.uid());
  create policy consents_insert on public.consents for insert to authenticated with check (user_id = auth.uid());
  create policy consents_withdraw on public.consents for update to authenticated
    using (user_id = auth.uid()) with check (user_id = auth.uid());

  create policy alerts_read on public.alerts for select to authenticated using (user_id = auth.uid());
exception when duplicate_object then null; end $$;

-- anonymous visitors never touch personal tables
revoke all on public.user_roles, public.boats, public.positions, public.push_subscriptions, public.share_grants,
              public.user_prefs, public.trips, public.consents, public.alerts from anon;
grant select, insert, update, delete on public.boats, public.positions, public.push_subscriptions,
              public.share_grants, public.user_prefs, public.trips to authenticated;
grant select, insert on public.user_roles to authenticated;
grant select, insert, update on public.consents to authenticated;
grant select on public.alerts to authenticated;
grant usage, select on all sequences in schema public to authenticated;

-- the worker sends pushes: it deletes subscriptions the push service reports gone (404/410, DeviceNotRegistered)
do $$ begin
  if exists (select from pg_roles where rolname = 'ty_worker') then
    grant select, insert, update on all tables in schema public to ty_worker;
    grant usage, select on all sequences in schema public to ty_worker;
    grant delete on public.push_subscriptions to ty_worker;
  end if;
end $$;
