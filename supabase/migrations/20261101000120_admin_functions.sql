-- Admin console reads and actions (spec §10.3). The web-facing API never holds a privileged role: each function
-- runs as its owner but first requires platform_admin with MFA (aal2) in the caller's JWT, and every action
-- writes the audit log. Live map and daily-use figures are aggregates with no user ids or coordinates.

create or replace function public.require_admin() returns void language plpgsql stable as $$
begin
  if not public.is_staff(array['platform_admin']) then
    raise exception 'platform_admin with MFA only' using errcode = '42501';
  end if;
end $$;

-- Overview + daily-use measures (prompt §13)
create or replace function public.admin_overview() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare day0 timestamptz := date_trunc('day', now() at time zone 'Asia/Kolkata') at time zone 'Asia/Kolkata';
begin
  perform public.require_admin();
  return jsonb_build_object(
    'answers_today', (select count(*) from public.answers where created_at >= day0),
    'guardrail_today', (select count(*) from public.answers where created_at >= day0 and (
        coalesce((guard->>'ungrounded_number')::int, 0) > 0 or coalesce((guard->>'quote_dropped')::int, 0) > 0
        or coalesce((guard->>'template_fallback')::boolean, false) or coalesce((guard->>'language_mismatch')::boolean, false))),
    'boats_at_sea', (select count(*) from public.trips where returned_at is null),
    'alerts_sent_today', (select count(*) from public.alerts where status = 'sent' and sent_at >= day0),
    'alerts_failed_today', (select count(*) from public.alerts where status = 'failed' and created_at >= day0),
    'briefs_sent_today', (select count(*) from public.alerts where kind = 'brief' and status = 'sent' and sent_at >= day0),
    'fishers', (select count(*) from public.user_roles where role = 'fisher'),
    'active_fishers_7d', (select count(distinct b.owner_id) from public.trips t join public.boats b on b.id = t.boat_id
                          where t.departed_at > now() - interval '7 days'),
    'trips_closed_7d', (select count(*) from public.trips where returned_at > now() - interval '7 days'),
    'feedback_rate_7d', (select round(avg(case when feedback is not null then 1.0 else 0 end), 2) from public.trips
                         where returned_at > now() - interval '7 days'),
    'right_rate_30d', (select round(avg(case when feedback = 'right' then 1.0 else 0 end), 2) from public.trips
                       where feedback is not null and returned_at > now() - interval '30 days'),
    'push_subscriptions', (select count(*) from public.push_subscriptions),
    'flags', (select jsonb_object_agg(key, value) from public.flags)
  );
end $$;

-- Alerts pipeline (no coordinates; user ids pseudonymised)
create or replace function public.admin_alerts(p_limit int default 100) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform public.require_admin();
  return coalesce((select jsonb_agg(x order by x.created_at desc) from (
    select a.id, a.kind, a.rule, a.critical, a.status, a.attempts, a.lang, a.title, a.created_at, a.sent_at,
           left(encode(extensions.digest(a.user_id::text, 'sha256'), 'hex'), 10) as user_ref
    from public.alerts a order by a.created_at desc limit least(p_limit, 500)) x), '[]'::jsonb);
end $$;

create or replace function public.admin_retry_alert(p_id uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform public.require_admin();
  update public.alerts set status = 'pending', attempts = 0 where id = p_id and status = 'failed';
  insert into public.audit_log (actor, action, target, detail) values (auth.uid(), 'alert.retry', p_id::text, '{}');
end $$;

-- Users & roles (staff see e-mails to manage access; never positions)
create or replace function public.admin_users() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform public.require_admin();
  return coalesce((select jsonb_agg(x order by x.created_at desc) from (
    select u.id, u.email, u.created_at, u.last_sign_in_at, coalesce(r.role::text, 'fisher') as role,
           exists (select 1 from auth.mfa_factors f where f.user_id = u.id and f.status = 'verified') as mfa,
           exists (select 1 from public.deletion_requests d where d.user_id = u.id) as deleting
    from auth.users u left join public.user_roles r on r.user_id = u.id) x), '[]'::jsonb);
end $$;

-- Live map: boats seen in the last hour as H3-free coarse cells (0.1°), counts only — anonymised
create or replace function public.admin_live_cells() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform public.require_admin();
  return coalesce((select jsonb_agg(x) from (
    select round(extensions.st_y(p.geom::extensions.geometry)::numeric, 1) as lat,
           round(extensions.st_x(p.geom::extensions.geometry)::numeric, 1) as lon, count(distinct p.boat_id) as boats
    from public.positions p where p.recorded_at > now() - interval '1 hour' group by 1, 2) x), '[]'::jsonb);
end $$;

-- Knowledge base: quarantine queue decisions and manual supersession
create or replace function public.admin_kb_decide(p_doc uuid, p_approve boolean, p_reason text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform public.require_admin();
  if p_approve then
    update public.kb_documents set status = 'active' where id = p_doc and status = 'quarantined';
  else
    delete from public.kb_chunks where document_id = p_doc
      and exists (select 1 from public.kb_documents d where d.id = p_doc and d.status = 'quarantined');
  end if;
  insert into public.audit_log (actor, action, target, detail)
  values (auth.uid(), case when p_approve then 'kb.approve' else 'kb.reject' end, p_doc::text,
          jsonb_build_object('reason', p_reason));
end $$;

create or replace function public.admin_kb_supersede(p_old uuid, p_new uuid, p_reason text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform public.require_admin();
  if p_old = p_new then raise exception 'a document cannot supersede itself' using errcode = '22023'; end if;
  update public.kb_documents set status = 'superseded', superseded_by = p_new, superseded_at = now()
   where id = p_old and status = 'active';
  if not found then raise exception 'document is not active' using errcode = '22023'; end if;
  insert into public.audit_log (actor, action, target, detail)
  values (auth.uid(), 'kb.supersede', p_old::text, jsonb_build_object('by', p_new, 'reason', p_reason));
end $$;

-- Guardrail review → failures dataset candidates (pulled into tests/failures/failures.yaml by a script + PR)
create table if not exists public.failure_candidates (
  id bigint generated always as identity primary key,
  answer_id uuid references public.answers(id) on delete set null,
  wrong text not null check (length(wrong) between 3 and 500),
  expect text check (length(expect) <= 500),
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  pulled_at timestamptz
);
alter table public.failure_candidates enable row level security;
grant select, insert on public.failure_candidates to authenticated;
do $$ begin
  create policy failures_admin on public.failure_candidates for all to authenticated
    using (public.is_staff(array['platform_admin'])) with check (public.is_staff(array['platform_admin']));
exception when duplicate_object then null; end $$;

do $$ begin
  if exists (select from pg_roles where rolname = 'ty_worker') then
    grant select, update on public.failure_candidates to ty_worker;
  end if;
end $$;

revoke all on function public.admin_overview(), public.admin_alerts(int), public.admin_retry_alert(uuid),
  public.admin_users(), public.admin_live_cells(), public.admin_kb_decide(uuid, boolean, text),
  public.admin_kb_supersede(uuid, uuid, text) from public, anon;
grant execute on function public.admin_overview(), public.admin_alerts(int), public.admin_retry_alert(uuid),
  public.admin_users(), public.admin_live_cells(), public.admin_kb_decide(uuid, boolean, text),
  public.admin_kb_supersede(uuid, uuid, text) to authenticated;
