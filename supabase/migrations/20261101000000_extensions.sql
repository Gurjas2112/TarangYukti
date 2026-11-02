-- Milestone 1: extensions needed by RAG (pgvector), geo filters (PostGIS) and ids.
create extension if not exists postgis with schema extensions;
create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;
