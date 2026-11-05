"""Story video assets for one language (spec §17.15): walkthrough capture → screenshots and clips; narration →
audio (Sarvam Bulbul for Group A, reviewer recordings for Group B); measured lengths → public/timeline.<lang>.json.

    cd services/channels && uv run python ../../video/scripts/build_assets.py <walkthrough-root> <lang> [--allow-missing]

A screen the script names but the capture lacks fails the build, unless --allow-missing: then the scene shows a
labelled "not captured in this build" card (a draft render; never a mock-up).
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

VIDEO = Path(__file__).resolve().parents[1]
REPO = VIDEO.parent
PUB = VIDEO / "public"
FONTS = REPO / "node_modules" / "@expo-google-fonts"
VOICE = "shubh"  # the app's Bulbul voice (services/channels voice.py), so the video sounds like the app
SCRIPT_FONT = {  # same Noto families as the app (apps/app/src/ui/fonts.ts)
    "Latn": "noto-sans/NotoSans", "Deva": "noto-sans-devanagari/NotoSansDevanagari",
    "Beng": "noto-sans-bengali/NotoSansBengali", "Taml": "noto-sans-tamil/NotoSansTamil",
    "Telu": "noto-sans-telugu/NotoSansTelugu", "Knda": "noto-sans-kannada/NotoSansKannada",
    "Mlym": "noto-sans-malayalam/NotoSansMalayalam", "Gujr": "noto-sans-gujarati/NotoSansGujarati",
    "Guru": "noto-sans-gurmukhi/NotoSansGurmukhi", "Orya": "noto-sans-oriya/NotoSansOriya",
    "Olck": "noto-sans-ol-chiki/NotoSansOlChiki", "Mtei": "noto-sans-meetei-mayek/NotoSansMeeteiMayek",
    "Nastaliq": "noto-nastaliq-urdu/NotoNastaliqUrdu", "Arab": "noto-naskh-arabic/NotoNaskhArabic",
}  # fmt: skip


def seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return float(out.strip() or 0)


def font_for(lang: dict[str, Any]) -> dict[str, str]:
    script = lang["script"]
    if script == "Arab":
        script = "Nastaliq" if lang["code"].startswith("ur") else "Arab"
    pkg, base = SCRIPT_FONT.get(script, SCRIPT_FONT["Latn"]).split("/")
    out = {}
    for weight, sub in (("regular", "400Regular"), ("bold", "700Bold")):
        src = FONTS / pkg / sub / f"{base}_{sub}.ttf"
        dst = PUB / "fonts" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        out[weight] = f"fonts/{src.name}"
    return out | {"family": base}


def narrate(scene: dict[str, Any], lang: dict[str, Any], tts: Any) -> Path:
    code = lang["code"]
    out = PUB / "audio" / code / f"{scene['id']}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    recorded = VIDEO / "recordings" / code / f"{scene['id']}.wav"
    if recorded.exists():  # Group B, or any language with a human recording
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(recorded), str(out)], check=True)
    elif lang["group"] == "A":
        if not out.exists():  # narration is cached until the script line changes (delete the file to redo)
            r = tts.text_to_speech.convert(
                text=scene["text"],
                language_code=lang["sarvam_code"],
                speaker=VOICE,
                model="bulbul:v3",
                output_audio_codec="mp3",
            )
            out.write_bytes(b"".join(base64.b64decode(x) for x in r.audios))
    else:
        raise SystemExit(f"{code}/{scene['id']}: no recording and no Bulbul voice for this language")
    return out


def cut(source: Path, start: float, length: float, name: str, code: str) -> str:
    out = PUB / "clips" / code / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(source),
         "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )  # fmt: skip
    return f"clips/{code}/{name}.mp4"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="artifacts/app-walkthrough/<version>-<date>")
    ap.add_argument("lang")
    ap.add_argument("--allow-missing", action="store_true")
    a = ap.parse_args()
    langs = {x["code"]: x for x in yaml.safe_load((REPO / "config/languages.yaml").read_text(encoding="utf-8"))["languages"]}
    L = langs[a.lang]
    src = a.root / a.lang
    script = yaml.safe_load((VIDEO / f"script/narration.{a.lang}.yaml").read_text(encoding="utf-8"))
    seg_file = src / "video" / "segments.json"
    segments = {s["flow"]: s for s in json.loads(seg_file.read_text())} if seg_file.exists() else {}

    from sarvamai import SarvamAI
    from ty_common.settings import get_settings

    key = get_settings().sarvam_api_key
    tts = SarvamAI(api_subscription_key=key.get_secret_value()) if key else None
    scenes, missing_all = [], []
    for sc in script["scenes"]:
        mp3 = narrate(sc, L, tts)
        entry: dict[str, Any] = {
            "id": sc["id"], "chapter": sc["chapter"], "kind": sc["kind"], "text": sc["text"],
            "narration": mp3.relative_to(PUB).as_posix(), "covers": sc.get("covers", []),
            "seconds": max(seconds(mp3) + 0.8, sc.get("min_seconds", 0)), "taps": sc.get("taps", []),
            "shots": [], "missing": [], "rtl": bool(L.get("rtl")), "art": sc.get("art"), "label": sc.get("label"),
        }  # fmt: skip
        for p in sc.get("shots", []):
            found = (a.root / p) if p.startswith("release-smoke/") else (src / p)
            if not found.exists():
                entry["missing"].append(p)
                continue
            dst = PUB / "shots" / a.lang / p
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(found, dst)
            entry["shots"].append(f"shots/{a.lang}/{p}")
        if "clip" in sc:
            c = sc["clip"]
            if c["flow"].startswith("W"):
                webm = next((src / "web").rglob(f"{c['flow']}*.webm"), None)
                if webm:
                    entry["clip"] = cut(webm, c["from"], c["to"] - c["from"], sc["id"], a.lang)
            elif c["flow"] in segments and (src / "video/full-walkthrough.mp4").exists():
                start = segments[c["flow"]]["startMs"] / 1000 + c["from"]
                entry["clip"] = cut(src / "video/full-walkthrough.mp4", start, c["to"] - c["from"], sc["id"], a.lang)
            if "clip" not in entry:
                entry["missing"].append(f"clip {c['flow']}")
            entry["seconds"] = max(entry["seconds"], c["to"] - c["from"])
        # each shot gets at least 2.5 s on screen
        entry["seconds"] = max(entry["seconds"], 2.5 * len(entry["shots"]))
        if entry["missing"]:
            missing_all.append(f"{sc['id']}: {', '.join(entry['missing'])}")
        scenes.append(entry)
    if missing_all and not a.allow_missing:
        print("missing in the capture:\n  " + "\n  ".join(missing_all), file=sys.stderr)
        raise SystemExit(1)
    timeline = {
        "lang": a.lang,
        "rtl": bool(L.get("rtl")),
        "font": font_for(L),
        "chapters": script["chapters"],
        "scenes": scenes,
    }
    (PUB / f"timeline.{a.lang}.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(s["seconds"] for s in scenes)
    print(f"{a.lang}: {len(scenes)} scenes, {total / 60:.1f} min, {len(missing_all)} scenes with missing screens")


if __name__ == "__main__":
    main()
