"""Dated source snapshots (prompt §7, spec §13.3 step 6).

A snapshot is one folder per day: `data/snapshot/<date>/` locally and `snapshots/<date>/` in the private
Supabase Storage bucket, each file wrapped as {"fetched_at", "source_url", "payload"} plus a
`manifest.json` with every file's SHA-256. `DATA_MODE=snapshot` reads only from here.

    uv run python -m tarangyukti.snapshot capture --date 2026-11-02 [--upload]
    uv run python -m tarangyukti.snapshot upload|download|verify --date 2026-11-02
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from ty_common.settings import get_settings

from . import config

BUCKET = "snapshots"
MANIFEST = "manifest.json"


class SnapshotMissing(FileNotFoundError):
    pass


class SnapshotStore:
    def __init__(self, date: str, root: Path | None = None) -> None:
        datetime.strptime(date, "%Y-%m-%d")  # validates the folder name
        self.date = date
        self.dir = (root or config.data_dir() / "snapshot") / date

    # files
    def write(self, name: str, payload: Any, source_url: str, fetched_at: datetime | None = None) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        doc = {
            "fetched_at": (fetched_at or datetime.now(UTC)).isoformat(),
            "source_url": source_url,
            "payload": payload,
        }
        (self.dir / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def read(self, name: str) -> dict[str, Any]:
        f = self.dir / f"{name}.json"
        if not f.is_file():
            raise SnapshotMissing(f"snapshot {self.date} has no {name}.json")
        doc: dict[str, Any] = json.loads(f.read_text(encoding="utf-8"))
        return doc

    def has(self, name: str) -> bool:
        return (self.dir / f"{name}.json").is_file()

    def files(self) -> list[Path]:
        return sorted(p for p in self.dir.glob("*.json") if p.name != MANIFEST)

    # manifest
    def write_manifest(self) -> dict[str, str]:
        m = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.files()}
        (self.dir / MANIFEST).write_text(json.dumps({"date": self.date, "files": m}, indent=1), encoding="utf-8")
        return m

    def verify(self) -> list[str]:
        """Names of files whose SHA-256 differs from the manifest (or that are missing)."""
        mf = self.dir / MANIFEST
        if not mf.is_file():
            return [MANIFEST]
        expected: dict[str, str] = json.loads(mf.read_text(encoding="utf-8"))["files"]
        bad = []
        for name, sha in expected.items():
            p = self.dir / name
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
                bad.append(name)
        return bad

    # Supabase Storage (service role key; never exposed to clients)
    def _storage(self) -> tuple[str, dict[str, str]]:
        s = get_settings()
        if s.supabase_service_role_key is None:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set")
        key = s.supabase_service_role_key.get_secret_value()
        return f"{s.supabase_url}/storage/v1", {"apikey": key, "Authorization": f"Bearer {key}"}

    async def ensure_bucket(self) -> None:
        base, h = self._storage()
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{base}/bucket/{BUCKET}", headers=h)
            if r.status_code == 200:
                return
            r = await c.post(f"{base}/bucket", headers=h, json={"id": BUCKET, "name": BUCKET, "public": False})
            if r.status_code not in (200, 201) and "already exists" not in r.text.lower():
                raise RuntimeError(f"cannot create bucket {BUCKET}: {r.status_code} {r.text[:200]}")

    async def upload(self) -> int:
        await self.ensure_bucket()
        base, h = self._storage()
        files = [*self.files(), self.dir / MANIFEST]
        async with httpx.AsyncClient(timeout=120) as c:
            for p in files:
                r = await c.post(
                    f"{base}/object/{BUCKET}/{self.date}/{p.name}",
                    headers=h | {"content-type": "application/json", "x-upsert": "true"},
                    content=p.read_bytes(),
                )
                r.raise_for_status()
        return len(files)

    async def download(self) -> int:
        base, h = self._storage()
        self.dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.get(f"{base}/object/{BUCKET}/{self.date}/{MANIFEST}", headers=h)
            if r.status_code != 200:
                raise SnapshotMissing(f"snapshot {self.date} not in Storage ({r.status_code})")
            (self.dir / MANIFEST).write_bytes(r.content)
            names = json.loads(r.content)["files"]
            for name in names:
                r = await c.get(f"{base}/object/{BUCKET}/{self.date}/{name}", headers=h)
                r.raise_for_status()
                (self.dir / name).write_bytes(r.content)
        bad = self.verify()
        if bad:
            raise RuntimeError(f"snapshot {self.date}: checksum mismatch in {bad}")
        return len(names)


def active_store() -> SnapshotStore | None:
    """The configured snapshot (SNAPSHOT_DATE), if one is set and present locally."""
    date = get_settings().snapshot_date
    if not date:
        return None
    store = SnapshotStore(date)
    return store if store.dir.is_dir() else None


# ── CLI ──────────────────────────────────────────────────────────────────────────


async def _capture(date: str, upload: bool) -> None:
    from .tools import cap, grids, marine  # imported here: tools import this module

    store = SnapshotStore(date)
    for name, coro in (
        ("marine", marine.capture_grid(store)),
        ("sst", grids.capture(store, "sst")),
        ("chl", grids.capture(store, "chl")),
        ("warnings_imd", cap.capture(store, "IMD")),
        ("warnings_incois", cap.capture(store, "INCOIS")),
    ):
        try:
            await coro
            print(f"captured {name}")
        except Exception as e:  # one source down must not lose the others
            print(f"FAILED {name}: {e}")
    if not store.has("pfz_incois"):
        print("note: pfz_incois.json not captured (INCOIS has no PFZ feed) - add it by hand")
    m = store.write_manifest()
    print(f"manifest: {len(m)} files in {store.dir}")
    if upload:
        print(f"uploaded {await store.upload()} files to Storage bucket '{BUCKET}/{date}'")


def main() -> None:
    ap = argparse.ArgumentParser(prog="tarangyukti.snapshot")
    ap.add_argument("action", choices=["capture", "upload", "download", "verify"])
    ap.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    ap.add_argument("--upload", action="store_true", help="with capture: also upload to Storage")
    a = ap.parse_args()
    store = SnapshotStore(a.date)
    if a.action == "capture":
        asyncio.run(_capture(a.date, a.upload))
    elif a.action == "upload":
        store.write_manifest()
        print(f"uploaded {asyncio.run(store.upload())} files")
    elif a.action == "download":
        print(f"downloaded {asyncio.run(store.download())} files")
    else:
        bad = store.verify()
        print("ok" if not bad else f"MISMATCH: {bad}")
        raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
