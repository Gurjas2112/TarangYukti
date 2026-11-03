-- Knowledge base (spec §6.2.3–6.2.4, Milestone 4).
create extension if not exists vector with schema extensions;
create extension if not exists postgis with schema extensions;

create table if not exists public.kb_documents (
  id uuid primary key default gen_random_uuid(),
  source_id text not null,                       -- stable id per logical document (e.g. 'dof:fishing-ban')
  version int not null default 1,
  title text not null,
  issuer text not null,                          -- 'INCOIS' | 'IMD' | 'SDMA' | 'DoF' | 'CMFRI' | 'TarangYukti'
  doc_type text not null check (doc_type in ('advisory','bulletin','order','act','method','statistics','sop')),
  language text not null,                        -- BCP-47, e.g. 'ta-IN', 'en-IN'
  url text not null,
  licence text not null,
  sha256 char(64) not null unique,
  valid_from timestamptz,
  valid_to timestamptz,
  region extensions.geography(MultiPolygon, 4326),
  status text not null default 'active' check (status in ('active','superseded','quarantined')),
  quarantine_reason text,
  ingested_at timestamptz not null default now(),          -- when TarangYukti learned it ("known at")
  superseded_by uuid references public.kb_documents(id),   -- the newer bulletin/order that replaces this one
  superseded_at timestamptz,                               -- when it was replaced (set with status = 'superseded')
  unique (source_id, version),
  check (valid_to is null or valid_from is null or valid_to > valid_from),
  check ((status = 'superseded') = (superseded_at is not null))
);
create index if not exists kb_documents_region on public.kb_documents using gist (region);
create index if not exists kb_documents_active on public.kb_documents (source_id) where status = 'active';

create table if not exists public.kb_chunks (
  id bigint generated always as identity primary key,
  document_id uuid not null references public.kb_documents(id) on delete cascade,
  ord int not null,
  heading_path text,
  content text not null check (length(content) between 20 and 6000),
  fts tsvector generated always as (to_tsvector('simple', content)) stored,   -- 'simple': works for every Indian script
  embedding extensions.vector(768) not null,                                   -- Gemini Embedding 2, 768-d
  embed_model text not null default 'gemini-embedding-2',
  index_version int not null,
  topics text[] not null default '{}',              -- canonical slugs from config/aliases.yaml, set at ingest
  unique (document_id, ord)
);
create index if not exists kb_chunks_fts on public.kb_chunks using gin (fts);
create index if not exists kb_chunks_topics on public.kb_chunks using gin (topics);
create index if not exists kb_chunks_emb on public.kb_chunks using hnsw (embedding extensions.vector_cosine_ops);

-- one row: the index version the query layer reads (bumped by every ingest run that changes chunks)
create table if not exists public.kb_index (
  id int primary key default 1 check (id = 1),
  index_version int not null default 0,
  updated_at timestamptz not null default now()
);
insert into public.kb_index (id) values (1) on conflict (id) do nothing;

create or replace function public.kb_hybrid_search(
  q_text text, q_emb extensions.vector(768),            -- q_emb null = full-text only (offline)
  at timestamptz default now(), near extensions.geography default null,
  k int default 40, rrf_k int default 50, known_at timestamptz default now())
returns table (chunk_id bigint, document_id uuid, content text, score double precision, sim double precision)
language sql stable
set search_path = public, extensions
as $$
  with eligible as (
    select c.id
    from kb_chunks c join kb_documents d on d.id = c.document_id
    where d.status <> 'quarantined'
      and d.ingested_at <= known_at                                         -- known by then
      and (d.superseded_at is null or d.superseded_at > known_at)          -- not yet replaced by then
      and (d.valid_from is null or d.valid_from <= at)
      and (d.valid_to   is null or d.valid_to   >  at)
      and (near is null or d.region is null or st_dwithin(d.region, near, 50000))
  ),
  ft as (
    select c.id, row_number() over (
             order by ts_rank_cd(c.fts, websearch_to_tsquery('simple', q_text)) desc) as r
    from kb_chunks c join eligible e on e.id = c.id
    where c.fts @@ websearch_to_tsquery('simple', q_text)
    order by r limit k
  ),
  sem as (
    select c.id, row_number() over (order by c.embedding <=> q_emb) as r
    from kb_chunks c join eligible e on e.id = c.id
    where q_emb is not null
    order by c.embedding <=> q_emb limit k
  )
  select c.id, c.document_id, c.content,
         coalesce(1.0 / (rrf_k + ft.r), 0) + coalesce(1.0 / (rrf_k + sem.r), 0) as score,
         case when q_emb is null then null else 1 - (c.embedding <=> q_emb) end as sim
  from ft full outer join sem on ft.id = sem.id
  join kb_chunks c on c.id = coalesce(ft.id, sem.id)
  order by score desc
  limit k;
$$;

-- RLS: read for everyone (public answers need no login), write only for the worker role (bypassrls)
alter table public.kb_documents enable row level security;
alter table public.kb_chunks enable row level security;
alter table public.kb_index enable row level security;
drop policy if exists kb_documents_read on public.kb_documents;
create policy kb_documents_read on public.kb_documents for select to anon, authenticated using (status <> 'quarantined');
drop policy if exists kb_chunks_read on public.kb_chunks;
create policy kb_chunks_read on public.kb_chunks for select to anon, authenticated
  using (exists (select 1 from public.kb_documents d where d.id = document_id and d.status <> 'quarantined'));
drop policy if exists kb_index_read on public.kb_index;
create policy kb_index_read on public.kb_index for select to anon, authenticated using (true);
grant select on public.kb_documents, public.kb_chunks, public.kb_index to anon, authenticated;
grant execute on function public.kb_hybrid_search to anon, authenticated;
