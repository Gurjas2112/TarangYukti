"""Draft every language's interface catalogue and safety phrase file from English (spec §6.5, Milestone 6/10a).

    cd services/channels && uv run python ../../scripts/i18n_draft.py [--only ta-IN ml-IN] [--force] [--sync-only]

1. Writes apps/app/src/i18n/languages.json from config/languages.yaml (the app cannot read YAML).
2. For each language other than English, translates the missing keys of apps/app/src/i18n/en-IN.json into
   apps/app/src/i18n/<code>.json and of config/phrases/en.yaml into config/phrases/<base>.yaml with Sarvam
   `sarvam-translate:v1` (formal, international numerals).

Every drafted phrase file is `status: draft` with no reviewers: machine translation never releases a safety
sentence (rule 6). A string keeps its English text when the translation lost or changed a {slot}, a {{variable}},
a number or a time; those keys are listed in apps/app/src/i18n/drafts.json for the reviewers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from sarvamai import AsyncSarvamAI
from ty_common.settings import get_settings

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "apps" / "app" / "src" / "i18n"
PHRASES = ROOT / "config" / "phrases"
KEEP_ENGLISH = {"app.title"}  # the product name
PHRASE_SKIP = {"status", "reviewers", "reviewed_on", "consent.notice_version"}
SLOT = re.compile(r"\{\{?\s*\w+\s*\}?\}")
NUM = re.compile(r"\d+(?:[.:]\d+)?")


def tokens(s: str) -> tuple[list[str], list[str]]:
    return sorted(SLOT.findall(s)), sorted(NUM.findall(SLOT.sub("", s)))


def flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def unflatten(flat: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, v in flat.items():
        cur = out
        parts = key.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return out


class Translator:
    def __init__(self, concurrency: int = 2) -> None:
        key = get_settings().sarvam_api_key
        if key is None:
            raise SystemExit("SARVAM_API_KEY is not set")
        self.client = AsyncSarvamAI(api_subscription_key=key.get_secret_value())
        self.sem = asyncio.Semaphore(concurrency)
        self.out_of_credit = False  # Sarvam 402: stop calling; remaining strings stay English (re-run later)

    async def one(self, text: str, target: str) -> str | None:
        """Translation, or None when it failed or changed a slot, number or time."""
        if self.out_of_credit:
            return None
        async with self.sem:
            for attempt in range(6):
                if self.out_of_credit:
                    return None
                try:
                    r = await self.client.text.translate(
                        input=text,
                        source_language_code="en-IN",
                        target_language_code=target,
                        model="sarvam-translate:v1",
                        mode="formal",
                        numerals_format="international",
                    )
                    break
                except Exception as e:  # rate limit or network: back off, then give up on this string
                    if getattr(e, "status_code", None) == 402:
                        if not self.out_of_credit:
                            print("  ! Sarvam: no credits left; remaining strings stay English", file=sys.stderr)
                        self.out_of_credit = True
                        return None
                    if attempt == 5:
                        print(f"  ! {target}: {type(e).__name__}", file=sys.stderr)
                        return None
                    await asyncio.sleep(2 ** (attempt + 1))
        out = str(r.translated_text).strip()
        return out if out and tokens(out) == tokens(text) else None


def sync_languages() -> list[dict[str, Any]]:
    langs = yaml.safe_load((ROOT / "config" / "languages.yaml").read_text(encoding="utf-8"))["languages"]
    keep = ("code", "sarvam_code", "name", "group", "script", "rtl", "status")
    data = [{k: x[k] for k in keep} for x in langs]
    (I18N / "languages.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return list(langs)


async def draft_language(tr: Translator, lang: dict[str, Any], force: bool, drafts: dict[str, Any]) -> None:
    code, target = lang["code"], lang["sarvam_code"]
    failed: list[str] = []

    # interface catalogue
    en_ui: dict[str, str] = json.loads((I18N / "en-IN.json").read_text(encoding="utf-8"))
    path = I18N / f"{code}.json"
    cur: dict[str, str] = {} if force or not path.is_file() else json.loads(path.read_text(encoding="utf-8"))
    cur = {k: v for k, v in cur.items() if k in en_ui and k not in drafts.get(code, {}).get("ui", [])}
    todo = [k for k in en_ui if k not in cur and k not in KEEP_ENGLISH]
    results = await asyncio.gather(*(tr.one(en_ui[k], target) for k in todo))
    for k, v in zip(todo, results, strict=True):
        cur[k] = v if v is not None else en_ui[k]
        if v is None:
            failed.append(k)
    for k in KEEP_ENGLISH:
        cur[k] = en_ui[k]
    ordered = {k: cur[k] for k in en_ui}
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # safety phrases (draft only)
    en_ph = yaml.safe_load((PHRASES / "en.yaml").read_text(encoding="utf-8"))
    ppath = PHRASES / f"{code.split('-')[0]}.yaml"
    old = {} if force or not ppath.is_file() else flatten(yaml.safe_load(ppath.read_text(encoding="utf-8")) or {})
    if old.get("status") == "approved":
        print(f"  {code}: phrase file is approved — not touched")
    else:
        en_flat = flatten(en_ph)
        prev_failed = set(drafts.get(code, {}).get("phrases", []))
        flat = {k: old[k] for k in en_flat if k in old and k not in prev_failed and k not in PHRASE_SKIP}
        todo = [k for k, v in en_flat.items() if k not in flat and k not in PHRASE_SKIP and isinstance(v, str)]
        results = await asyncio.gather(*(tr.one(en_flat[k], target) for k in todo))
        pfailed = []
        for k, v in zip(todo, results, strict=True):
            flat[k] = v if v is not None else en_flat[k]
            if v is None:
                pfailed.append(k)
        for k in PHRASE_SKIP:
            if k in en_flat:
                flat[k] = en_flat[k]
        flat.update({"status": "draft", "reviewers": [], "reviewed_on": None})
        doc = unflatten({k: flat[k] for k in en_flat})
        header = (
            f"# {lang['name']} ({code}) — DRAFT machine translation (sarvam-translate:v1) of config/phrases/en.yaml.\n"
            "# Not released: two native-speaker reviewers must check and sign every sentence (spec §6.5, SR-14).\n"
            "# Governed file: language owner.\n"
        )
        body = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1000)
        ppath.write_text(header + body, encoding="utf-8")
        failed += [f"phrases:{k}" for k in pfailed]

    drafts[code] = {
        "ui": [k for k in failed if not k.startswith("phrases:")],
        "phrases": [k.removeprefix("phrases:") for k in failed if k.startswith("phrases:")],
    }
    print(f"  {code}: {len(failed)} strings kept in English")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sync-only", action="store_true")
    a = ap.parse_args()
    langs = sync_languages()
    if a.sync_only:
        return
    dpath = I18N / "drafts.json"
    drafts: dict[str, Any] = json.loads(dpath.read_text(encoding="utf-8")) if dpath.is_file() else {}
    tr = Translator()
    for lang in langs:
        if lang["code"].startswith("en") or (a.only and lang["code"] not in a.only):
            continue
        print(f"{lang['code']} …")
        await draft_language(tr, lang, a.force, drafts)
        dpath.write_text(json.dumps(drafts, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
