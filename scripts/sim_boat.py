"""Simulated boat trip (spec §17.11, prompt §15 Milestone 8): out of the harbour, toward the border line until the
5 km and 2 km rings are crossed, then back into the harbour circle.

    cd services/mcp
    uv run python ../../scripts/sim_boat.py --gpx ../../artifacts/sim_trip.gpx          # Android emulator route
    uv run python ../../scripts/sim_boat.py --post --email ty-test-fisher@example.com    # → ty-channels /positions

--post (ENV=local only) signs in as a dev account through the Supabase admin API (the same one-time token the
"Add this phone" QR uses) and sends the fixes with source "simulated", oldest first, in batches; --realtime sends
one fix per --interval seconds instead. The track never contains a real person's position.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

import httpx
from tarangyukti.tools.geo import fence_check
from ty_common.phrases import harbour
from ty_common.settings import get_settings

KNOTS_KMH = 1.852


def step_towards(lat: float, lon: float, brg_deg: float, km: float) -> tuple[float, float]:
    d = km / 6371.0088
    b = math.radians(brg_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def track(harbour_id: str, bearing: float, stop_km: float, speed_kn: float, interval_s: int) -> list[tuple[float, float]]:
    """Points every `interval_s` at `speed_kn` along `bearing` until the border is `stop_km` away, then back."""
    h = harbour(harbour_id)
    step = speed_kn * KNOTS_KMH * interval_s / 3600
    pts = [(h["lat"], h["lon"])]
    while True:
        lat, lon = step_towards(*pts[-1], bearing, step)
        f = fence_check(lat, lon)["data"]
        pts.append((lat, lon))
        if f["imbl_km"] <= stop_km or f["side"] == "beyond_imbl" or len(pts) > 500:
            break
    for _ in range(3):  # linger at the far point (a few minutes of fishing)
        pts.append(pts[-1])
    return pts + list(reversed(pts[:-1]))


def gpx(points: list[tuple[float, float]], start: datetime, interval_s: int) -> str:
    rows = "\n".join(
        f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}"><time>{(start + timedelta(seconds=i * interval_s)).isoformat()}'
        f"</time></trkpt>"
        for i, (lat, lon) in enumerate(points)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="TarangYukti sim_boat" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n  <trk><name>'
        + escape("Simulated trip (SIMULATION)")
        + "</name><trkseg>\n"
        + rows
        + "\n  </trkseg></trk>\n</gpx>\n"
    )


def dev_session(email: str) -> tuple[str, str]:
    """(access token, boat id) for a dev account — local only."""
    s = get_settings()
    if s.env == "live":
        raise SystemExit("refusing to mint a session with ENV=live")
    if s.supabase_service_role_key is None:
        raise SystemExit("SUPABASE_SERVICE_ROLE_KEY is not set")
    k = s.supabase_service_role_key.get_secret_value()
    pub = next(
        line.split("=", 1)[1].strip()
        for line in (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8").splitlines()
        if line.startswith("SUPABASE_PUBLISHABLE_KEY=")
    )
    h = {"apikey": k, "Authorization": f"Bearer {k}"}
    with httpx.Client(timeout=20) as c:
        r = c.post(f"{s.supabase_url}/auth/v1/admin/generate_link", headers=h, json={"type": "magiclink", "email": email})
        r.raise_for_status()
        th = r.json().get("hashed_token") or r.json()["properties"]["hashed_token"]
        v = c.post(f"{s.supabase_url}/auth/v1/verify", headers={"apikey": pub}, json={"type": "magiclink", "token_hash": th})
        v.raise_for_status()
        token = v.json()["access_token"]
        me = c.get(f"{channels()}/me", headers={"Authorization": f"Bearer {token}"})
        me.raise_for_status()
        boats = me.json()["boats"]
    if not boats:
        raise SystemExit(f"{email} has no boat — finish onboarding first")
    return token, boats[0]["id"]


def channels() -> str:
    return "http://127.0.0.1:8002"


def main() -> None:
    ap = argparse.ArgumentParser(prog="sim_boat")
    ap.add_argument("--harbour", default="rameswaram")
    ap.add_argument("--bearing", type=float, default=75.0, help="degrees from north (default: east-north-east)")
    ap.add_argument("--stop-km", type=float, default=1.5, help="turn back when the border line is this close")
    ap.add_argument("--speed", type=float, default=7.0, help="knots")
    ap.add_argument("--interval", type=int, default=60, help="seconds between fixes")
    ap.add_argument("--gpx", type=Path)
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--email", default="ty-test-fisher@example.com")
    ap.add_argument("--realtime", action="store_true")
    a = ap.parse_args()

    pts = track(a.harbour, a.bearing, a.stop_km, a.speed, a.interval)
    nearest = min(fence_check(lat, lon)["data"]["imbl_km"] for lat, lon in pts)
    print(f"{len(pts)} fixes, {len(pts) * a.interval // 60} min, closest to the border: {nearest} km", file=sys.stderr)
    start = datetime.now(UTC) - timedelta(seconds=a.interval * len(pts)) if not a.realtime else datetime.now(UTC)

    if a.gpx:
        a.gpx.parent.mkdir(parents=True, exist_ok=True)
        a.gpx.write_text(gpx(pts, start, a.interval), encoding="utf-8")
        print(f"wrote {a.gpx}", file=sys.stderr)
    if not a.post:
        return
    token, boat = dev_session(a.email)
    fixes = [
        {"lat": round(lat, 6), "lon": round(lon, 6), "recorded_at": (start + timedelta(seconds=i * a.interval)).isoformat(),
         "speed_knots": a.speed}
        for i, (lat, lon) in enumerate(pts)
    ]
    batches = [[f] for f in fixes] if a.realtime else [fixes[i : i + 25] for i in range(0, len(fixes), 25)]
    with httpx.Client(timeout=120, headers={"Authorization": f"Bearer {token}"}) as c:
        for b in batches:
            if a.realtime:
                b[0]["recorded_at"] = datetime.now(UTC).isoformat()
            r = c.post(f"{channels()}/positions", json={"boat_id": boat, "source": "simulated", "fixes": b})
            r.raise_for_status()
            d = r.json()
            print(f"{b[-1]['recorded_at'][11:16]}Z border {d['border']['km']} km {d['border']['ring']:8} "
                  f"events={d['events']} alerts={d['alerts']}", file=sys.stderr)
            if a.realtime:
                time.sleep(a.interval)


if __name__ == "__main__":
    main()
