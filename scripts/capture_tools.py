"""Small helpers for the capture shell scripts (spec §17.14.4), so they need no jq or inline Python.

    python scripts/capture_tools.py scenario <flow|scenario>          → scenario name
    python scripts/capture_tools.py segment <segments.json> <flow> <startMs> <endMs>
    python scripts/capture_tools.py collect <from-dir>… --to <android-dir>   (Maestro screenshots by flow/step)
    python scripts/capture_tools.py manifest <out.json> <lang> <avd> <video-seconds> [failed flows…]
    python scripts/capture_tools.py released                           → released language codes
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "normal", "brief-now", "simulated-warning", "no-safe-window", "stale-data", "llm-offline",
    "kill-switch-chat", "fault-next-request", "update-required", "font-scale-200",
}  # fmt: skip


def scenario(arg: str) -> str:
    if arg in SCENARIOS:
        return arg
    m = yaml.safe_load((ROOT / "apps/app/e2e/maestro/scenarios.yaml").read_text(encoding="utf-8")) or {}
    return str(m.get(arg, "normal"))


def segment(path: str, flow: str, start: str, end: str) -> None:
    p = Path(path)
    d = json.loads(p.read_text()) if p.is_file() else []
    d.append({"flow": flow, "startMs": int(start), "endMs": int(end)})
    p.write_text(json.dumps(d, indent=1))


def collect(args: list[str]) -> int:
    """Move every <flow>/<step>.png that Maestro wrote (in its output dir or the working dir) under `--to`."""
    to = Path(args[args.index("--to") + 1])
    n = 0
    for base in [Path(a) for a in args[: args.index("--to")]]:
        # Maestro writes `takeScreenshot: <flow>/<step>` relative to the working directory: there, only its own
        # top-level <flow>/ folders are taken, never anything deeper (the repo holds earlier captures).
        pngs = base.glob("[AR][0-9][0-9]-*/*.png") if base.resolve() == Path.cwd().resolve() else base.rglob("*.png")
        for png in pngs:
            flow = png.parent.name
            if not (len(flow) > 4 and flow[0] in "AR" and flow[1:3].isdigit() and flow[3] == "-"):
                continue
            dest = to / flow / png.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(png), dest)
            n += 1
        for d in sorted(base.glob("[AR][0-9][0-9]-*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    return n


def manifest(out: str, lang: str, avd: str, seconds: str, failed: list[str]) -> None:
    Path(out).write_text(
        json.dumps(
            {
                "language": lang,
                "emulator": avd,
                "androidVideoSeconds": float(seconds or 0),
                "androidFlowsFailed": failed,
                "androidFlowsPassed": not failed,
                "capturedAt": datetime.now(UTC).isoformat(),
            },
            indent=1,
        )
    )


def released() -> str:
    langs = yaml.safe_load((ROOT / "config/languages.yaml").read_text(encoding="utf-8"))["languages"]
    return " ".join(x["code"] for x in langs if x["status"] == "released")


def main() -> None:
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "scenario":
        print(scenario(args[0]))
    elif cmd == "segment":
        segment(*args[:4])
    elif cmd == "collect":
        print(collect(args))
    elif cmd == "manifest":
        manifest(args[0], args[1], args[2], args[3], args[4:])
    elif cmd == "released":
        print(released())
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
