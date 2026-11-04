-- The app path a push opens (e.g. /brief?harbour=…&boat=…&lang=…). Never coordinates.
alter table public.alerts add column if not exists url text
  check (url is null or (url like '/%' and length(url) <= 300 and url !~ '\d+\.\d{3,}'));
