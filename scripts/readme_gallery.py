"""Flow-by-flow screenshot gallery for the root README, from a walkthrough capture (spec §17.14).

    python scripts/readme_gallery.py <walkthrough-root> [--lang en-IN] [--video-url URL] [--preview docs/media/…mp4]

Copies every captured screenshot of `lang` into docs/screenshots/<platform>/<flow>/<step>.png, scaled down (phone
540 px wide, browser 960 px) so the repository stays light, and replaces the README sections between
<!-- WALKTHROUGH-GALLERY --> and <!-- WALKTHROUGH-VIDEO --> markers. Real captures only: a flow with no screenshot is
listed as not captured, never filled in.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "screenshots"
FLOW_TITLES = {
    "A01-onboarding": "Getting started in your language",
    "A02-morning-brief": "The morning brief",
    "A03-today": "Today: the verdict and why",
    "A04-map": "The map (works offline)",
    "A05-ask": "Ask anything",
    "A06-catch-dropped": "Why has my catch dropped?",
    "A07-out-of-coverage": "Outside its coverage",
    "A08-trip": "At sea: trip mode and border alerts",
    "A09-alerts": "Alerts",
    "A10-family": "Family sharing",
    "A11-me": "Me: data, language, help",
    "A12-add-phone": "Add this phone",
    "A13-simulated-warning": "Official warning wins (simulation)",
    "A14-no-safe-window": "No safe window",
    "A15-stale-data": "Old data is never 'good to go'",
    "A16-llm-offline": "AI offline: buttons still work",
    "A17-kill-switch": "Free chat switched off",
    "A18-error-retry": "Error and retry",
    "A19-update": "Update required",
    "A20-large-text": "Large text (200 %)",
    "A21-rtl": "Right-to-left (Urdu)",
    "W01-public": "Public web verdict",
    "W02-staff-sign-in": "Staff sign-in",
    "W03-expert": "Expert console",
    "W04-analyst": "Analyst tools",
    "W05-officer": "District officer",
    "W06-admin": "Admin console",
    "W07-family-web": "Family on the web",
    "W08-accessibility": "Web: right-to-left and zoom",
    "R01-release-smoke": "Release build on the live environment",
}


def scale(src: Path, dst: Path, width: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", f"scale='min({width},iw)':-2", str(dst)],
        check=True,
    )


def gallery(root: Path, lang: str) -> tuple[str, int, int]:
    features = yaml.safe_load((REPO / "apps/app/e2e/coverage.yaml").read_text(encoding="utf-8"))["features"]
    flows: dict[str, list[dict]] = {}
    for f in features:
        flows.setdefault(f["flow"], []).append(f)
    lines: list[str] = []
    shots = captured_flows = 0
    for flow, feats in flows.items():
        plat = feats[0]["platform"]
        base = root / "release-smoke" if plat == "release" else root / lang / ("web" if plat == "web" else "android")
        found = []
        for f in feats:
            for s in f["shots"]:
                src = base / flow / f"{s}.png"
                if src.exists():
                    sub = "web" if plat == "web" else "android"
                    rel = Path(sub) / flow / f"{s}.png"
                    scale(src, OUT / rel, 960 if plat == "web" else 540)
                    found.append((s, rel.as_posix()))
        names = " · ".join(f["feature"].split(";")[0] for f in feats)
        title = FLOW_TITLES.get(flow, flow)
        lines.append(f"<details{' open' if flow in ('A03-today', 'W03-expert') else ''}>")
        plural = "s" if len(found) != 1 else ""
        lines.append(f"<summary><b>{flow[:3]} · {title}</b> — {len(found)} screen{plural}</summary>")
        lines.append("")
        lines.append(f"*{names}*")
        lines.append("")
        if not found:
            lines.append(
                "_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._"
            )
        else:
            captured_flows += 1
            shots += len(found)
            width = 420 if plat == "web" else 200
            lines.append("<p>")
            for s, rel in found:
                lines.append(
                    f'<img src="docs/screenshots/{rel}" width="{width}" alt="{flow} {s}" title="{s}">'
                )
            lines.append("</p>")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    return "\n".join(lines), shots, captured_flows


def replace(readme: str, marker: str, body: str) -> str:
    pat = re.compile(rf"<!-- {marker} -->.*?(?=\n## |\Z)", re.S)
    return pat.sub(lambda _: f"<!-- {marker} -->\n\n{body}\n", readme, count=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--lang", default="en-IN")
    ap.add_argument("--video-url", default=None, help="full-length recording (GitHub release asset)")
    ap.add_argument("--preview", default=None, help="compressed preview committed to the repo")
    a = ap.parse_args()
    body, shots, flows = gallery(a.root, a.lang)
    intro = (
        f"Every screen below is a real capture of this build (Android emulator and Chrome, {a.lang}), taken "
        f"automatically by the walkthrough flows in `apps/app/e2e/` — **{shots} screens across {flows} flows**. "
        "Click a flow to open it.\n\n"
    )
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    readme = replace(readme, "WALKTHROUGH-GALLERY", intro + body)
    video = []
    if a.preview:
        video.append(f"https://github.com/Gurjas2112/TarangYukti/raw/main/{a.preview}\n")
        video.append(f"*The full-length recording, compressed for the repository ({Path(a.preview).name}).*")
    if a.video_url:
        video.append(
            f"\n**[⬇ Full-length screen recording, every flow in order]({a.video_url})** — uncut, from the emulator, "
            "with every screenshot and the capture manifest in the same release."
        )
    if video:
        readme = replace(readme, "WALKTHROUGH-VIDEO", "\n".join(video))
    (REPO / "README.md").write_text(readme, encoding="utf-8")
    print(f"gallery: {shots} screens, {flows} flows")


if __name__ == "__main__":
    main()
