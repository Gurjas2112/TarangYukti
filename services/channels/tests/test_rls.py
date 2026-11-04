"""Row-level security across users (Milestone 9, spec §8.4, §16 Security). Runs against the real database as ty_api
(no BYPASSRLS) with each test user's JWT claims, so Postgres policies decide — not application code.

Needs the dev accounts ty-test-fisher@ and ty-test-family@example.com (the fisher's boat shared with the family
account; see scripts/sim_boat.py) and DATABASE_URL / WORKER_DATABASE_URL / SUPABASE_DB_URL in .env.

    RLS_TESTS=1 uv run pytest -q tests/test_rls.py        # make test-rls
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row
from ty_common.settings import get_settings

pytestmark = pytest.mark.skipif(os.environ.get("RLS_TESTS") != "1", reason="needs the dev database (RLS_TESTS=1)")

PERSONAL = [
    "boats",
    "positions",
    "trips",
    "push_subscriptions",
    "consents",
    "alerts",
    "share_grants",
    "user_prefs",
    "answers",
    "deletion_requests",
    "user_roles",
]


def url(name: str) -> str:
    v = getattr(get_settings(), name)
    assert v is not None, f"{name} is not set"
    return str(v.get_secret_value())


@pytest.fixture(scope="module")
def ids() -> dict[str, str]:
    with psycopg.connect(url("supabase_db_url"), row_factory=dict_row) as c:
        rows = c.execute(
            "select id, email from auth.users where email = any(%s)",
            (["ty-test-fisher@example.com", "ty-test-family@example.com"],),
        ).fetchall()
        by = {r["email"]: str(r["id"]) for r in rows}
        boat = c.execute(
            "select id from public.boats where owner_id = %s", (by["ty-test-fisher@example.com"],)
        ).fetchone()
    assert boat, "the fisher test account needs a boat (onboarding)"
    return {
        "fisher": by["ty-test-fisher@example.com"],
        "family": by["ty-test-family@example.com"],
        "stranger": str(uuid.uuid4()),
        "boat": str(boat["id"]),
    }


@contextmanager
def as_user(sub: str | None, **extra: Any) -> Iterator[psycopg.Cursor[dict[str, Any]]]:
    """One transaction as `authenticated` with these claims (sub=None → `anon`); always rolled back."""
    with psycopg.connect(url("database_url"), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if sub is None:
                cur.execute("set local role anon")
            else:
                claims = {"sub": sub, "role": "authenticated", "aal": "aal1", **extra}
                cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
                cur.execute("set local role authenticated")
            try:
                yield cur
            finally:
                conn.rollback()


def count(cur: psycopg.Cursor[dict[str, Any]], table: str) -> int:
    cur.execute(f"select count(*) as n from public.{table}")
    row = cur.fetchone()
    return int(row["n"]) if row else 0


def test_a_stranger_sees_none_of_the_fishers_data(ids: dict[str, str]) -> None:
    with as_user(ids["fisher"]) as cur:
        assert count(cur, "boats") >= 1
    with as_user(ids["stranger"]) as cur:
        for t in PERSONAL:
            assert count(cur, t) == 0, t


def test_anonymous_cannot_read_personal_tables(ids: dict[str, str]) -> None:
    for t in PERSONAL:
        with as_user(None) as cur:
            try:
                n = count(cur, t)
            except psycopg.errors.InsufficientPrivilege:
                continue
            assert n == 0, t


def test_family_sees_the_shared_boat_but_cannot_write_its_positions(ids: dict[str, str]) -> None:
    with as_user(ids["family"]) as cur:
        cur.execute("select id from public.boats where id = %s", (ids["boat"],))
        assert cur.fetchone() is not None
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute(
                """insert into public.positions (boat_id, geom, recorded_at, source)
                   values (%s, extensions.st_makepoint(79.3, 9.3)::extensions.geography, now(), 'web_live')""",
                (ids["boat"],),
            )


def test_a_revoked_grant_hides_the_boat(ids: dict[str, str]) -> None:
    with psycopg.connect(url("worker_database_url"), row_factory=dict_row) as w:
        g = w.execute(
            "select id from public.share_grants where boat_id = %s and revoked_at is null and grantee_id = %s",
            (ids["boat"], ids["family"]),
        ).fetchone()
        assert g, "share the fisher's boat with the family account first"
        w.execute("update public.share_grants set revoked_at = now() where id = %s", (g["id"],))
        w.commit()
        try:
            with as_user(ids["family"]) as cur:
                cur.execute("select id from public.boats where id = %s", (ids["boat"],))
                assert cur.fetchone() is None
        finally:
            w.execute("update public.share_grants set revoked_at = null where id = %s", (g["id"],))
            w.commit()


def test_push_subscriptions_are_private(ids: dict[str, str]) -> None:
    with as_user(ids["family"]) as cur:
        cur.execute("select count(*) as n from public.push_subscriptions where user_id = %s", (ids["fisher"],))
        assert cur.fetchone()["n"] == 0  # type: ignore[index]


def test_alerts_can_only_be_queued_for_your_own_boat(ids: dict[str, str]) -> None:
    with as_user(ids["family"]) as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cur.execute("select public.queue_boat_alert(%s, 'border-2km', 't', 'b', 'en-IN')", (ids["boat"],))
    with as_user(ids["fisher"]) as cur, pytest.raises(psycopg.errors.InvalidParameterValue):
        cur.execute("select public.queue_boat_alert(%s, 'free-fish', 't', 'b', 'en-IN')", (ids["boat"],))


def test_users_cannot_make_themselves_staff(ids: dict[str, str]) -> None:
    with as_user(ids["stranger"]) as cur, pytest.raises(psycopg.errors.Error):
        cur.execute("insert into public.user_roles (user_id, role) values (%s, 'platform_admin')", (ids["stranger"],))
    with as_user(ids["fisher"], app_role="fisher") as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cur.execute("select public.set_role(%s, 'platform_admin', 'escalate')", (ids["fisher"],))


def test_admin_functions_need_admin_with_mfa(ids: dict[str, str]) -> None:
    with (
        as_user(ids["fisher"], app_role="platform_admin", aal="aal1") as cur,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        cur.execute("select public.admin_overview()")
    with as_user(ids["fisher"], app_role="platform_admin", aal="aal2") as cur:
        cur.execute("select public.admin_overview() as o")
        assert "answers_today" in cur.fetchone()["o"]  # type: ignore[index]
        assert count(cur, "audit_log") >= 0


def test_officer_sees_only_boats_inside_active_warnings_with_mfa(ids: dict[str, str]) -> None:
    area = {
        "type": "MultiPolygon",
        "coordinates": [[[[79.2, 9.2], [79.5, 9.2], [79.5, 9.5], [79.2, 9.5], [79.2, 9.2]]]],
    }
    with psycopg.connect(url("worker_database_url"), row_factory=dict_row) as w:
        w.execute(
            """insert into public.warning_areas (id, issuer, title, geom, valid_from, valid_to)
               values ('TEST-RLS', 'INCOIS', 'SIMULATION test area',
                       extensions.st_geomfromgeojson(%s)::extensions.geography, now() - interval '1 hour',
                       now() + interval '1 hour')""",
            (json.dumps(area),),
        )
        inside = w.execute(
            """insert into public.positions (boat_id, geom, recorded_at, source) values
               (%s, extensions.st_setsrid(extensions.st_makepoint(79.35, 9.35), 4326)::extensions.geography, now(),
                'simulated') returning id""",
            (ids["boat"],),
        ).fetchone()
        outside = w.execute(
            """insert into public.positions (boat_id, geom, recorded_at, source) values
               (%s, extensions.st_setsrid(extensions.st_makepoint(79.0, 9.0), 4326)::extensions.geography, now(),
                'simulated') returning id""",
            (ids["boat"],),
        ).fetchone()
        w.commit()
        try:
            officer = str(uuid.uuid4())
            with as_user(officer, app_role="officer", aal="aal2") as cur:
                cur.execute("select id from public.positions where id in (%s, %s)", (inside["id"], outside["id"]))  # type: ignore[index]
                assert [r["id"] for r in cur.fetchall()] == [inside["id"]]  # type: ignore[index]
            with as_user(officer, app_role="officer", aal="aal1") as cur:
                assert count(cur, "positions") == 0
        finally:
            w.execute("delete from public.positions where id in (%s, %s)", (inside["id"], outside["id"]))  # type: ignore[index]
            w.execute("delete from public.warning_areas where id = 'TEST-RLS'")
            w.commit()


def test_audit_chain_detects_tampering() -> None:
    with psycopg.connect(url("supabase_db_url"), row_factory=dict_row) as c:
        c.execute("insert into public.audit_log (action, target, detail) values ('system.test', 'rls', '{}')")
        assert c.execute("select public.audit_verify() as b").fetchone()["b"] is None  # type: ignore[index]
        row = c.execute("select id from public.audit_log order by id desc limit 1").fetchone()
        c.execute("update public.audit_log set detail = '{\"tampered\": true}' where id = %s", (row["id"],))  # type: ignore[index]
        assert c.execute("select public.audit_verify() as b").fetchone()["b"] == row["id"]  # type: ignore[index]
        c.rollback()  # nothing is kept


# ── the admin API end to end through channels (real database; the JWT check is replaced by fixed claims) ──────


@pytest.fixture
def admin_client(ids: dict[str, str]) -> Iterator[Any]:
    import asyncio
    import sys

    from fastapi.testclient import TestClient

    from ty_channels import admin
    from ty_channels.app import app

    if sys.platform == "win32":  # psycopg's async driver needs a selector loop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
    claims = {"sub": ids["fisher"], "role": "authenticated", "app_role": "platform_admin", "aal": "aal2"}
    app.dependency_overrides[admin.admin_only] = lambda: claims
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_admin_api_end_to_end(admin_client: Any) -> None:
    c = admin_client
    o = c.get("/admin/overview").json()
    assert {"answers_today", "boats_at_sea", "alerts_failed_today", "flags"} <= set(o)
    assert c.post("/admin/audit/verify").json() == {"intact": True, "first_broken_id": None}
    users = c.get("/admin/users").json()["users"]
    assert any(u["email"] == "ty-test-fisher@example.com" for u in users)
    assert all("lat" in x and "boats" in x for x in c.get("/admin/live").json()["cells"])
    assert c.get("/admin/kb").json()["documents"]
    # kill switch round trip, both audit-logged
    assert c.post("/admin/flags/free_chat_off", json={"value": True, "reason": "rls test"}).status_code == 200
    assert c.get("/admin/overview").json()["flags"]["free_chat_off"] is True
    assert c.post("/admin/flags/free_chat_off", json={"value": False, "reason": "rls test done"}).status_code == 200
    assert c.post("/admin/flags/free_chat_off", json={"value": [], "reason": "bad"}).status_code == 422
    events = c.get("/admin/audit").json()["events"]
    assert [e["action"] for e in events[:2]] == ["flag.set", "flag.set"]
    assert c.post("/admin/audit/verify").json()["intact"] is True


def test_agent_role_records_answers_and_reads_switches_only() -> None:
    with psycopg.connect(url("agent_database_url"), row_factory=dict_row) as c:
        c.execute(
            """insert into public.answers (thread_id, lang, mode, model, prompt_version, config_version)
               values ('rls-test', 'en-IN', 'simple', 'test', 'test', 'test')"""
        )
        assert c.execute("select value from public.flags where key = 'free_chat_off'").fetchone() is not None
        for table in ("positions", "boats", "push_subscriptions", "answers"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(f"select 1 from public.{table} limit 1")
            c.rollback()
        c.rollback()
