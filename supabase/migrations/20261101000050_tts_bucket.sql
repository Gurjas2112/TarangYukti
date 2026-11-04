-- Spoken approved phrases and briefs (cache namespace `tts`, spec §7a): mp3 objects named by
-- sha256(text, voice, model). Public read: the audio is the same for everyone and holds no personal data.
-- Only channels (service role) writes.
insert into storage.buckets (id, name, public, allowed_mime_types, file_size_limit)
values ('tts', 'tts', true, array['audio/mpeg'], 2097152)
on conflict (id) do nothing;
