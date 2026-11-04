-- Milestone 8: trips, boat alerts, family sharing (spec §6.6, §9.1.3; prompt §10.5–10.7).

-- one open trip per boat; the worker stamps the family notice once
alter table public.trips add column if not exists family_notified_at timestamptz;
create unique index if not exists trips_one_open on public.trips (boat_id) where returned_at is null;
create index if not exists positions_boat_time on public.positions (boat_id, recorded_at desc);

-- Boat alerts raised by channels while checking a live position (border rings, marine park). Runs as the caller:
-- the caller must own the boat, the rule must be one of these, and "critical" follows the rule, so a user can
-- only ever queue these alerts for themselves. The worker sends them (one sender) after the alert budget.
create or replace function public.queue_boat_alert(p_boat uuid, p_rule text, p_title text, p_body text, p_lang text)
returns uuid language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); aid uuid;
begin
  if uid is null or not exists (select 1 from public.boats b where b.id = p_boat and b.owner_id = uid) then
    raise exception 'not your boat' using errcode = '42501';
  end if;
  if p_rule not in ('border-5km', 'border-2km', 'beyond-imbl', 'mpa') then
    raise exception 'unknown alert rule %', p_rule using errcode = '22023';
  end if;
  insert into public.alerts (user_id, boat_id, kind, rule, critical, title, body, lang, url)
  values (uid, p_boat, 'alert', p_rule, p_rule <> 'mpa', left(p_title, 120), left(p_body, 500), p_lang, '/alerts')
  returning id into aid;
  return aid;
end $$;
revoke all on function public.queue_boat_alert(uuid, text, text, text, text) from public, anon;
grant execute on function public.queue_boat_alert(uuid, text, text, text, text) to authenticated;

-- Family: a fisher shares a boat with an e-mail address; when that person signs in, the pending grants for their
-- verified e-mail are attached to their account and they get the `family` role (if they have no role yet).
create or replace function public.claim_share_grants() returns int
language plpgsql security definer set search_path = '' as $$
declare uid uuid := auth.uid(); mail text := lower(auth.jwt() ->> 'email'); n int;
begin
  if uid is null or mail is null then return 0; end if;
  update public.share_grants set grantee_id = uid
   where grantee_id is null and lower(grantee_email) = mail and revoked_at is null and expires_at > now();
  get diagnostics n = row_count;
  if n > 0 then
    insert into public.user_roles (user_id, role) values (uid, 'family') on conflict do nothing;
  end if;
  return n;
end $$;
revoke all on function public.claim_share_grants() from public, anon;
grant execute on function public.claim_share_grants() to authenticated;

-- grant e-mails are personal data: only the boat owner reads them (grants_owner); the grantee reads its own rows
alter table public.share_grants add constraint share_grants_email_shape
  check (grantee_email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$') not valid;
alter table public.share_grants add constraint share_grants_max_90_days
  check (expires_at <= created_at + interval '90 days') not valid;
