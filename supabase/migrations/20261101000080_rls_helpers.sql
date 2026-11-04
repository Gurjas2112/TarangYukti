-- boats ↔ share_grants policies referenced each other (infinite recursion). Two security-definer helpers answer
-- "does the caller own this boat?" and "does the caller hold a live grant for it?" without re-entering RLS.
create or replace function public.owns_boat(b uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.boats where id = b and owner_id = auth.uid())
$$;
create or replace function public.has_boat_grant(b uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.share_grants g where g.boat_id = b and g.grantee_id = auth.uid()
                 and g.revoked_at is null and g.expires_at > now())
$$;
revoke all on function public.owns_boat(uuid), public.has_boat_grant(uuid) from public, anon;
grant execute on function public.owns_boat(uuid), public.has_boat_grant(uuid) to authenticated;

drop policy if exists boats_family on public.boats;
create policy boats_family on public.boats for select to authenticated using (public.has_boat_grant(id));

drop policy if exists grants_owner on public.share_grants;
create policy grants_owner on public.share_grants for all to authenticated
  using (public.owns_boat(boat_id)) with check (public.owns_boat(boat_id));

drop policy if exists positions_owner_or_family on public.positions;
create policy positions_owner_or_family on public.positions for select to authenticated
  using (public.owns_boat(boat_id) or public.has_boat_grant(boat_id));
drop policy if exists positions_owner_insert on public.positions;
create policy positions_owner_insert on public.positions for insert to authenticated
  with check (public.owns_boat(boat_id));

drop policy if exists trips_owner_or_family on public.trips;
create policy trips_owner_or_family on public.trips for select to authenticated
  using (public.owns_boat(boat_id) or public.has_boat_grant(boat_id));
drop policy if exists trips_owner_write on public.trips;
create policy trips_owner_write on public.trips for all to authenticated
  using (public.owns_boat(boat_id)) with check (public.owns_boat(boat_id));
