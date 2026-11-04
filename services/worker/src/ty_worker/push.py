"""One push sender, two transports (spec §6.8): Expo push for the Android app, Web Push (VAPID) for the web build.

`send()` returns True (delivered to the push service), False (temporary failure, retry) or None (the
subscription is gone: 404/410 from a web push service or DeviceNotRegistered from Expo), in which case the row
is deleted. Payloads carry an alert id, a kind, short text and an app path, never coordinates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal, TypedDict

import httpx
from psycopg import AsyncConnection
from pywebpush import WebPushException, webpush
from ty_common.settings import Settings, get_settings

log = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
Kind = Literal["web", "expo"]


class Message(TypedDict):
    id: str
    kind: str  # brief | alert | family | test
    title: str
    body: str
    url: str  # app path, e.g. /brief?harbour=rameswaram&boat=small_frp&lang=ta-IN


async def _expo(sub: dict[str, Any], msg: Message, urgent: bool, s: Settings) -> bool | None:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if s.expo_access_token is not None:
        headers["Authorization"] = f"Bearer {s.expo_access_token.get_secret_value()}"
    payload = {
        "to": sub["endpoint"],
        "title": msg["title"],
        "body": msg["body"],
        "data": {"id": msg["id"], "kind": msg["kind"], "url": msg["url"]},
        "priority": "high" if urgent else "normal",
        "channelId": "danger" if urgent else "default",
        "ttl": 3600 if urgent else 4 * 3600,
        "sound": "default",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(EXPO_PUSH_URL, headers=headers, json=payload)
        r.raise_for_status()
        ticket = r.json()["data"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        log.warning("expo push failed: %s", type(e).__name__)
        return False
    if isinstance(ticket, list):
        ticket = ticket[0]
    if ticket.get("status") == "error":
        if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
            return None
        log.warning("expo push error: %s", ticket.get("details", {}).get("error"))
        return False
    return True


def _web_sync(sub: dict[str, Any], msg: Message, urgent: bool, s: Settings) -> bool | None:
    if s.vapid_private_key is None:
        log.warning("web push skipped: VAPID_PRIVATE_KEY not set")
        return False
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=json.dumps(msg),
            vapid_private_key=s.vapid_private_key.get_secret_value(),
            vapid_claims={"sub": s.vapid_subject},
            ttl=3600 if urgent else 4 * 3600,
            headers={"Urgency": "high" if urgent else "normal"},
            timeout=10,
        )
        return True
    except WebPushException as ex:
        if ex.response is not None and ex.response.status_code in (404, 410):
            return None
        log.warning("web push failed: %s", ex.response.status_code if ex.response is not None else "no response")
        return False


async def send(sub: dict[str, Any], msg: Message, *, urgent: bool, conn: AsyncConnection[Any]) -> bool:
    s = get_settings()
    ok = (
        await _expo(sub, msg, urgent, s)
        if sub["kind"] == "expo"
        else await asyncio.to_thread(_web_sync, sub, msg, urgent, s)
    )
    if ok is None:  # subscription is gone
        await conn.execute("delete from push_subscriptions where id = %s", (sub["id"],))
        return False
    if ok:
        await conn.execute("update push_subscriptions set last_ok_at = now() where id = %s", (sub["id"],))
    return ok
