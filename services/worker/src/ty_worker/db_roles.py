"""Create the service login roles (spec §13.10) and write their connection strings into the repo .env.

Same roles as scripts/db_roles.sh, for machines without psql. Passwords are generated here, applied with
ALTER ROLE and written only to the git-ignored .env (DATABASE_URL, WORKER_DATABASE_URL, AGENT_DATABASE_URL).
Re-running rotates the passwords.

    uv run python -m ty_worker.db_roles
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from psycopg import sql
from ty_common.settings import find_config_dir, get_settings

ROLES = {  # role → (.env variable, attributes)
    "ty_api": ("DATABASE_URL", "login noinherit"),  # no BYPASSRLS: every request runs as `authenticated`
    "ty_worker": ("WORKER_DATABASE_URL", "login bypassrls"),  # jobs across users; never web-reachable
    "ty_agent": ("AGENT_DATABASE_URL", "login noinherit"),  # schema `agent` only (Milestone 5)
}

GRANTS = """
grant authenticated to ty_api;
grant anon to ty_api;
grant usage on schema public to ty_worker;
grant select, insert, update on all tables in schema public to ty_worker;
grant usage, select on all sequences in schema public to ty_worker;
alter default privileges in schema public grant select, insert, update on tables to ty_worker;
alter default privileges in schema public grant usage, select on sequences to ty_worker;
grant usage on schema extensions to ty_worker, ty_api;
do $$ begin
  if exists (select from pg_namespace where nspname = 'agent') then
    grant usage, create on schema agent to ty_agent;
    grant select, insert, update, delete on all tables in schema agent to ty_agent;
    alter default privileges in schema agent grant select, insert, update, delete on tables to ty_agent;
    grant usage on schema agent to ty_worker;
    grant select, delete on all tables in schema agent to ty_worker;
    alter default privileges in schema agent grant select, delete on tables to ty_worker;
  end if;
end $$;
"""


def with_user(admin_url: str, user: str, password: str) -> str:
    u = urlsplit(admin_url)
    host = u.hostname or ""
    netloc = f"{user}:{quote(password, safe='')}@{host}" + (f":{u.port}" if u.port else "")
    return urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment))


def update_env(env: Path, values: dict[str, str]) -> None:
    text = env.read_text(encoding="utf-8")
    for key, val in values.items():
        line = f"{key}={val}"
        text, n = re.subn(rf"^{key}=.*$", line.replace("\\", "\\\\"), text, flags=re.M)
        if n == 0:
            text += f"\n{line}\n"
    env.write_text(text, encoding="utf-8")


def main() -> None:
    secret = get_settings().supabase_db_url
    if secret is None:
        raise SystemExit("SUPABASE_DB_URL is not set")
    admin = secret.get_secret_value()
    urls: dict[str, str] = {}
    with psycopg.connect(admin, autocommit=True) as conn:
        for role, (var, attrs) in ROLES.items():
            pw = secrets.token_urlsafe(24)
            exists = conn.execute("select 1 from pg_roles where rolname = %s", (role,)).fetchone()
            verb = "alter" if exists else "create"
            conn.execute(
                sql.SQL("{} role {} with {} password {}").format(
                    sql.SQL(verb), sql.Identifier(role), sql.SQL(attrs), sql.Literal(pw)
                )
            )
            urls[var] = with_user(admin, role, pw)
            print(f"{verb}d role {role}")
        conn.execute(GRANTS.encode())
    env = find_config_dir().parent / ".env"
    update_env(env, urls)
    print(f"wrote {', '.join(urls)} to {env}")


if __name__ == "__main__":
    main()
