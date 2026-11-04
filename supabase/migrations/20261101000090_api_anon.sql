-- ty_api serves public reads (citations, document list) as `anon`, under the same RLS as the Data API.
do $$ begin
  if exists (select from pg_roles where rolname = 'ty_api') then
    grant anon to ty_api;
  end if;
end $$;
