-- ty_agent is not BYPASSRLS: it needs its own policies to record answers and read the kill switches.
do $$ begin
  if exists (select from pg_roles where rolname = 'ty_agent') then
    begin
      create policy answers_agent_insert on public.answers for insert to ty_agent with check (true);
    exception when duplicate_object then null; end;
    begin
      create policy flags_agent_read on public.flags for select to ty_agent using (true);
    exception when duplicate_object then null; end;
  end if;
end $$;
