-- Dated data snapshots (spec §13.3 step 6). Private: only the service role (mcp, worker) reads it.
insert into storage.buckets (id, name, public) values ('snapshots', 'snapshots', false)
on conflict (id) do nothing;
-- no storage.objects policies for anon/authenticated
