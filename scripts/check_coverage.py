"""Walkthrough coverage check (spec §17.14.4): every feature in apps/app/e2e/coverage.yaml has every screenshot
in every captured language, and a scene in that language's story-video narration (Milestone 12).

    python scripts/check_coverage.py <walkthrough-root> --langs ml-IN hi-IN [--skip-video]

Writes <root>/README.md (feature × language matrix linking each image, TODO captions for the reviewer) and
<root>/coverage-report.json, and exits 1 on any gap. `--skip-video` reports scene gaps without failing,
for captures made before the story video exists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]


def shot_path(root: Path, lang: str, f: dict[str, Any], shot: str) -> Path:
    if f["platform"] == "release":
        return root / "release-smoke" / f["flow"] / f"{shot}.png"
    sub = "web" if f["platform"] == "web" else "android"
    return root / lang / sub / f["flow"] / f"{shot}.png"


def scenes_for(lang: str) -> set[str] | None:
    """Feature IDs covered by the story video's narration for `lang`, or None when there is no narration file."""
    p = REPO / "video" / "script" / f"narration.{lang}.yaml"
    if not p.is_file():
        return None
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    covered: set[str] = set()
    for scene in doc.get("scenes", []):
        covered.update(scene.get("covers", []))
    return covered


def check(root: Path, langs: list[str], skip_video: bool) -> tuple[dict[str, Any], bool]:
    features = yaml.safe_load((REPO / "apps/app/e2e/coverage.yaml").read_text(encoding="utf-8"))["features"]
    report: dict[str, Any] = {"root": str(root), "languages": langs, "features": []}
    ok = True
    for f in features:
        row: dict[str, Any] = {"id": f["id"], "feature": f["feature"], "flow": f["flow"], "languages": {}}
        for lang in langs:
            found = [s for s in f["shots"] if shot_path(root, lang, f, s).is_file()]
            missing = [s for s in f["shots"] if s not in found]
            scenes = scenes_for(lang)
            scene = None if scenes is None else f["id"] in scenes
            row["languages"][lang] = {"found": found, "missing": missing, "scene": scene}
            if missing or (scene is not True and not skip_video):
                ok = False
        report["features"].append(row)
    report["complete"] = ok
    return report, ok


def readme(report: dict[str, Any]) -> str:
    langs = report["languages"]
    root = Path(report["root"])
    lines = [
        "# Kadal Mitra walkthrough",
        "",
        "Every feature (apps/app/e2e/coverage.yaml) × every captured language. ✅ all screenshots, "
        "◐ some, ❌ none; 🎬 the story video has a scene for it. Captions are written after reading each image.",
        "",
        "| ID | Feature | " + " | ".join(langs) + " |",
        "|---|---|" + "---|" * len(langs),
    ]
    for row in report["features"]:
        cells = []
        for lang in langs:
            c = row["languages"][lang]
            n, m = len(c["found"]), len(c["missing"])
            mark = "✅" if m == 0 else ("❌" if n == 0 else "◐")
            cells.append(f"{mark} {n}/{n + m}" + (" 🎬" if c["scene"] else ""))
        lines.append(f"| {row['id']} | {row['feature']} | " + " | ".join(cells) + " |")
    lines += ["", "## Screenshots", ""]
    for row in report["features"]:
        for lang in langs:
            for shot in row["languages"][lang]["found"]:
                f = {"platform": _platform(row["flow"]), "flow": row["flow"]}
                rel = shot_path(root, lang, f, shot).relative_to(root).as_posix()
                lines.append(f"- {row['id']} · {lang} · [{row['flow']}/{shot}]({rel}) — TODO caption")
    gaps = [
        f"- {row['id']} {lang}: missing {', '.join(c['missing']) or '—'}"
        + ("" if c["scene"] else " · no video scene")
        for row in report["features"]
        for lang, c in row["languages"].items()
        if c["missing"] or not c["scene"]
    ]
    if gaps:
        lines += ["", "## Gaps", "", *gaps]
    return "\n".join(lines) + "\n"


def _platform(flow: str) -> str:
    return "web" if flow.startswith("W") else ("release" if flow.startswith("R") else "android")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--langs", nargs="+", required=True)
    ap.add_argument("--skip-video", action="store_true")
    a = ap.parse_args()
    report, ok = check(a.root, a.langs, a.skip_video)
    a.root.mkdir(parents=True, exist_ok=True)
    (a.root / "coverage-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.root / "README.md").write_text(readme(report), encoding="utf-8")
    shots = sum(len(c["found"]) for r in report["features"] for c in r["languages"].values())
    total = sum(len(c["found"]) + len(c["missing"]) for r in report["features"] for c in r["languages"].values())
    complete = sum(all(not c["missing"] for c in r["languages"].values()) for r in report["features"])
    print(f"coverage: {shots}/{total} screenshots, {complete}/{len(report['features'])} features complete")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
