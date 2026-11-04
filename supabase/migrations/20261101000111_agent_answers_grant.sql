-- The agent records every reply in public.answers and reads the kill switches (follow-up to 000110).
do $$ begin
  if exists (select from pg_roles where rolname = 'ty_agent') then
    grant usage on schema public to ty_agent;
    grant insert on public.answers to ty_agent;
    grant select on public.flags to ty_agent;
  end if;
end $$;
