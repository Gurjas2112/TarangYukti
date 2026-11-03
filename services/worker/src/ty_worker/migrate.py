"""Apply supabase/migrations/*.sql to the database at SUPABASE_DB_URL (admin), in order, once each.

Applied versions are recorded in supabase_migrations.schema_migrations, the same table the Supabase CLI
uses, so `supabase db push` and this runner agree on what is applied.

    uv run python -m ty_worker.migrate [--dry-run]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg
from ty_common.settings import find_config_dir, get_settings

SETUP = """
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (
  version text primary key, statements text[], name text
);
"""


def migrations_dir() -> Path:
    return find_config_dir().parent / "supabase" / "migrations"


def pending(conn: psycopg.Connection) -> list[Path]:
    done = {r[0] for r in conn.execute("select version from supabase_migrations.schema_migrations")}
    return [p for p in sorted(migrations_dir().glob("*.sql")) if p.name.split("_", 1)[0] not in done]


def main() -> None:
    ap = argparse.ArgumentParser(prog="ty_worker.migrate")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    secret = get_settings().supabase_db_url
    url = secret.get_secret_value() if secret else None
    if not url:
        raise SystemExit("SUPABASE_DB_URL is not set (admin connection; never used by services)")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SETUP)
        todo = pending(conn)
        if not todo:
            print("database is up to date")
        for p in todo:
            version, name = p.stem.split("_", 1)
            print(f"{'would apply' if a.dry_run else 'applying'} {p.name}")
            if a.dry_run:
                continue
            sql = p.read_text(encoding="utf-8")
            with conn.transaction():
                conn.execute(sql.encode())  # trusted file from the repo
                conn.execute(
                    "insert into supabase_migrations.schema_migrations (version, statements, name) values (%s, %s, %s)",
                    (version, [sql], name),
                )


if __name__ == "__main__":
    main()
