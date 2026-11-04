-- A user may queue only the "alerts are on" test push for themselves (channels /push/subscribe);
-- every other alert is written by the worker. The worker sends it (one sender).
grant insert on public.alerts to authenticated;
do $$ begin
  create policy alerts_test_insert on public.alerts for insert to authenticated
    with check (user_id = auth.uid() and kind = 'test' and not critical and status = 'pending');
exception when duplicate_object then null; end $$;
