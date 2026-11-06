<div align="center">

# 🌊 TarangYukti · Kadal Mitra

### *"Can I go to sea today?"* — answered in your own language, with the reasons, before you leave the harbour.

**TarangYukti** (तरंग *wave* + युक्ति *reasoning*) turns ISRO / INCOIS ocean data, IMD warnings and official fishing
documents into a clear **Go · Careful · Don't go** for small-boat fishers — and keeps watching the border line for them
at sea, even with the phone locked and no signal.

[![CI](https://github.com/Gurjas2112/TarangYukti/actions/workflows/ci.yml/badge.svg)](https://github.com/Gurjas2112/TarangYukti/actions/workflows/ci.yml)
![Languages](https://img.shields.io/badge/languages-22%20Indian%20%2B%20English-F26B21)
![Platforms](https://img.shields.io/badge/app-Android%20%2B%20Web-2F6FDE)
![AI](https://img.shields.io/badge/AI-explains,%20rules%20decide-07612A)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[▶ Watch the full walkthrough](#-see-it-in-action)** · **[🖼 Screens, flow by flow](#-flow-by-flow)** ·
**[🌐 Try the web app](https://ty-web.wittybay-bae06624.centralindia.azurecontainerapps.io)** ·
**[⚙ How it works](#-how-it-works)** · **[🚀 Run it](#-run-it-yourself)**

</div>

---

> **Advisory only — always follow official INCOIS / IMD warnings.** TarangYukti is a prototype for the Gulf of Mannar
> and Palk Bay (Smart India Hackathon 2026, ISRO problem statement 26176, "ORCA").

## 💡 Why it exists

At 4:30 in the morning a fisher in Rameswaram has one question. The answer is scattered across wave forecasts,
official warnings, long English bulletins and a border line nobody can see at sea — crossing it can cost the boat
and the crew's freedom. **Kadal Mitra** (*friend of the sea*), the app, puts it all into one card:

| You ask | You get |
|---|---|
| 🗣 "Can I go to sea tomorrow morning?" — by voice or a tap, in Tamil, Hindi, Malayalam, Urdu… | **Go · Careful · Don't go**, a good time to leave, when to be back, and *why* in one sentence |
| 🐟 "Where should I fish?" | Likely fishing zones on a map that works offline, with the border line and the marine park |
| ⚖ "When is the fishing ban?" | The official document, quoted word for word, with its source |
| ⛵ *(nothing — you're at sea)* | Automatic alerts **5 km** and **2 km** from the border line, with the screen off and no signal |
| 🏠 *(your family at home)* | "He is back at the harbour" — without calling |

## ✨ What makes it different

- **🧮 The AI never invents a number.** Every wave height, distance and time comes from a tool with a source and a
  timestamp. A validator rejects any reply with a figure it cannot trace — then falls back to approved sentences.
- **⚖ Rules decide, the AI explains.** Go / Careful / Don't go comes from a deterministic constraint engine
  (*Yukti*: 8 hard rules, 5 soft) and a time-aware safest-route search — not from a language model.
- **🚨 Official warnings always win.** An active INCOIS or IMD warning forces *Don't go*. The app never says "safe" —
  only "advisory".
- **🇮🇳 Every Indian language, none built in.** All 22 scheduled languages + English: interface, voice in (and voice out
  for 11), Noto fonts for every script, right-to-left for Urdu, Kashmiri and Sindhi. Safety sentences are released only
  after two native speakers sign them.
- **📴 Works where the signal doesn't.** Border and park checks run on the phone; positions queue offline and sync later.
- **🔍 Every answer can be audited.** Each verdict is stored as a ledger of rules, values and datasets, with the time each
  fact was true and the time it was known — so any past answer can be replayed.

## 🎬 See it in action

<!-- WALKTHROUGH-VIDEO -->

<table><tr><td width="320" valign="top">

<img src="docs/media/kadal-mitra-hero.gif" width="300" alt="Kadal Mitra: choosing a language, harbour and boat, then the verdict card">

</td><td valign="top">

**[▶ Watch the full-length screen recording](docs/media/kadal-mitra-walkthrough.mp4)** — 9 min 9 s, uncut: all
22 Android flows in order, recorded on the emulator by the automated walkthrough (`make capture`). Compressed to
5 MB for the repository.

What you will see, in order: choosing a language → harbour → boat → consent · the morning brief · the verdict, its
reasons and the 24-hour ribbon · the offline map · asking questions (border distance, fishing ban, *why has my
catch dropped?*, an out-of-region question) · alerts · your data, help and privacy · a labelled **SIMULATION**
of an official warning forcing *Don't go* · no safe window · old data · AI offline · chat switched off · an
error and *Try again* · an update prompt · 200 % text · right-to-left Urdu.

Every frame is the real app — nothing mocked up.

</td></tr></table>

## 🖼 Flow by flow

<!-- WALKTHROUGH-GALLERY -->

Every screen below is a real capture of this build (Android emulator and Chrome, en-IN), taken automatically by the walkthrough flows in `apps/app/e2e/` — **51 screens across 22 flows**. Click a flow to open it.

<details>
<summary><b>A01 · Getting started in your language</b> — 6 screens</summary>

*Language picker with every language in its own script, spoken where a voice exists · Harbour list · Boat type picture buttons · Spoken consent, full written notice · Location, notification and background-location permissions with explanation · Google sign-in*

<p>
<img src="docs/screenshots/android/A01-onboarding/01-language-picker.png" width="200" alt="A01-onboarding 01-language-picker" title="01-language-picker">
<img src="docs/screenshots/android/A01-onboarding/02-language-spoken.png" width="200" alt="A01-onboarding 02-language-spoken" title="02-language-spoken">
<img src="docs/screenshots/android/A01-onboarding/03-harbour.png" width="200" alt="A01-onboarding 03-harbour" title="03-harbour">
<img src="docs/screenshots/android/A01-onboarding/04-boat.png" width="200" alt="A01-onboarding 04-boat" title="04-boat">
<img src="docs/screenshots/android/A01-onboarding/05-consent.png" width="200" alt="A01-onboarding 05-consent" title="05-consent">
<img src="docs/screenshots/android/A01-onboarding/06-full-notice.png" width="200" alt="A01-onboarding 06-full-notice" title="06-full-notice">
</p>

</details>

<details>
<summary><b>A12 · Add this phone</b> — 0 screens</summary>

*"Add this phone" QR link*

_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._

</details>

<details>
<summary><b>A02 · The morning brief</b> — 2 screens</summary>

*Morning brief push, opened from the notification, voice plays*

<p>
<img src="docs/screenshots/android/A02-morning-brief/02-brief-card.png" width="200" alt="A02-morning-brief 02-brief-card" title="02-brief-card">
<img src="docs/screenshots/android/A02-morning-brief/03-voice-playing.png" width="200" alt="A02-morning-brief 03-voice-playing" title="03-voice-playing">
</p>

</details>

<details open>
<summary><b>A03 · Today: the verdict and why</b> — 4 screens</summary>

*Verdict card GO / CAUTION / NO-GO, 24-hour ribbon · "Why?" in one sentence, then all reasons · Four buttons*

<p>
<img src="docs/screenshots/android/A03-today/01-verdict.png" width="200" alt="A03-today 01-verdict" title="01-verdict">
<img src="docs/screenshots/android/A03-today/02-ribbon.png" width="200" alt="A03-today 02-ribbon" title="02-ribbon">
<img src="docs/screenshots/android/A03-today/03-why.png" width="200" alt="A03-today 03-why" title="03-why">
<img src="docs/screenshots/android/A03-today/05-four-buttons.png" width="200" alt="A03-today 05-four-buttons" title="05-four-buttons">
</p>

</details>

<details>
<summary><b>A04 · The map (works offline)</b> — 2 screens</summary>

*Where to fish: PFZ, agreement with INCOIS · Safest route, border line, protected area, own position, offline tiles*

<p>
<img src="docs/screenshots/android/A04-map/01-pfz.png" width="200" alt="A04-map 01-pfz" title="01-pfz">
<img src="docs/screenshots/android/A04-map/04-border-mpa.png" width="200" alt="A04-map 04-border-mpa" title="04-border-mpa">
</p>

</details>

<details>
<summary><b>A05 · Ask anything</b> — 3 screens</summary>

*Ask: voice button, instant acknowledgement · Cited answer with verbatim quote and labelled translation*

<p>
<img src="docs/screenshots/android/A05-ask/01-mic.png" width="200" alt="A05-ask 01-mic" title="01-mic">
<img src="docs/screenshots/android/A05-ask/02-checking.png" width="200" alt="A05-ask 02-checking" title="02-checking">
<img src="docs/screenshots/android/A05-ask/03-answer.png" width="200" alt="A05-ask 03-answer" title="03-answer">
</p>

</details>

<details>
<summary><b>A06 · Why has my catch dropped?</b> — 2 screens</summary>

*"Why has catch dropped?" ranked causes*

<p>
<img src="docs/screenshots/android/A06-catch-dropped/01-question.png" width="200" alt="A06-catch-dropped 01-question" title="01-question">
<img src="docs/screenshots/android/A06-catch-dropped/02-causes.png" width="200" alt="A06-catch-dropped 02-causes" title="02-causes">
</p>

</details>

<details>
<summary><b>A07 · Outside its coverage</b> — 1 screen</summary>

*Out-of-coverage refusal naming the official source*

<p>
<img src="docs/screenshots/android/A07-out-of-coverage/01-refusal.png" width="200" alt="A07-out-of-coverage 01-refusal" title="01-refusal">
</p>

</details>

<details>
<summary><b>A08 · At sea: trip mode and border alerts</b> — 0 screens</summary>

*Trip mode starts on leaving the harbour · Border alerts at 5 km and 2 km · Offline at sea: map, route, brief and alerts work · "I'm back", trip closed*

_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._

</details>

<details>
<summary><b>A09 · Alerts</b> — 1 screen</summary>

*Alerts list with reasons*

<p>
<img src="docs/screenshots/android/A09-alerts/01-list.png" width="200" alt="A09-alerts 01-list" title="01-list">
</p>

</details>

<details>
<summary><b>A10 · Family sharing</b> — 0 screens</summary>

*Family sharing: grant with expiry*

_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._

</details>

<details>
<summary><b>A11 · Me: data, language, help</b> — 4 screens</summary>

*Me: profile and boats · Language switch to any language, including right-to-left · Consent history and withdrawal · Help with grievance officer*

<p>
<img src="docs/screenshots/android/A11-me/01-profile.png" width="200" alt="A11-me 01-profile" title="01-profile">
<img src="docs/screenshots/android/A11-me/04-language-switch.png" width="200" alt="A11-me 04-language-switch" title="04-language-switch">
<img src="docs/screenshots/android/A11-me/08-help-grievance.png" width="200" alt="A11-me 08-help-grievance" title="08-help-grievance">
<img src="docs/screenshots/android/A11-me/09-about-privacy.png" width="200" alt="A11-me 09-about-privacy" title="09-about-privacy">
</p>

</details>

<details>
<summary><b>A13 · Official warning wins (simulation)</b> — 2 screens</summary>

*Simulated official warning forces NO-GO, labelled SIMULATION*

<p>
<img src="docs/screenshots/android/A13-simulated-warning/01-nogo-simulation.png" width="200" alt="A13-simulated-warning 01-nogo-simulation" title="01-nogo-simulation">
<img src="docs/screenshots/android/A13-simulated-warning/02-why-warning.png" width="200" alt="A13-simulated-warning 02-why-warning" title="02-why-warning">
</p>

</details>

<details>
<summary><b>A14 · No safe window</b> — 1 screen</summary>

*No safe window: next good time*

<p>
<img src="docs/screenshots/android/A14-no-safe-window/01-no-window.png" width="200" alt="A14-no-safe-window 01-no-window" title="01-no-window">
</p>

</details>

<details>
<summary><b>A15 · Old data is never 'good to go'</b> — 1 screen</summary>

*Stale data: old forecast, never Good to go*

<p>
<img src="docs/screenshots/android/A15-stale-data/01-stale.png" width="200" alt="A15-stale-data 01-stale" title="01-stale">
</p>

</details>

<details>
<summary><b>A16 · AI offline: buttons still work</b> — 2 screens</summary>

*LLM unreachable: buttons answer from templates*

<p>
<img src="docs/screenshots/android/A16-llm-offline/01-templates-only.png" width="200" alt="A16-llm-offline 01-templates-only" title="01-templates-only">
<img src="docs/screenshots/android/A16-llm-offline/02-free-form-offline.png" width="200" alt="A16-llm-offline 02-free-form-offline" title="02-free-form-offline">
</p>

</details>

<details>
<summary><b>A17 · Free chat switched off</b> — 1 screen</summary>

*Kill switch: free-form chat off, buttons and alerts on*

<p>
<img src="docs/screenshots/android/A17-kill-switch/01-chat-off.png" width="200" alt="A17-kill-switch 01-chat-off" title="01-chat-off">
</p>

</details>

<details>
<summary><b>A18 · Error and retry</b> — 2 screens</summary>

*Error with retry*

<p>
<img src="docs/screenshots/android/A18-error-retry/01-error.png" width="200" alt="A18-error-retry 01-error" title="01-error">
<img src="docs/screenshots/android/A18-error-retry/02-retried.png" width="200" alt="A18-error-retry 02-retried" title="02-retried">
</p>

</details>

<details>
<summary><b>A19 · Update required</b> — 1 screen</summary>

*Update available banner*

<p>
<img src="docs/screenshots/android/A19-update/02-update-required.png" width="200" alt="A19-update 02-update-required" title="02-update-required">
</p>

</details>

<details>
<summary><b>A20 · Large text (200 %)</b> — 2 screens</summary>

*Large text at 200 % without clipping*

<p>
<img src="docs/screenshots/android/A20-large-text/01-today-200.png" width="200" alt="A20-large-text 01-today-200" title="01-today-200">
<img src="docs/screenshots/android/A20-large-text/02-map-200.png" width="200" alt="A20-large-text 02-map-200" title="02-map-200">
</p>

</details>

<details>
<summary><b>W01 · Public web verdict</b> — 2 screens</summary>

*Public web verdict without login*

<p>
<img src="docs/screenshots/web/W01-public/01-public-verdict.png" width="420" alt="W01-public 01-public-verdict" title="01-public-verdict">
<img src="docs/screenshots/web/W01-public/02-install.png" width="420" alt="W01-public 02-install" title="02-install">
</p>

</details>

<details>
<summary><b>W02 · Staff sign-in</b> — 1 screen</summary>

*Staff sign-in with Google and TOTP (aal2)*

<p>
<img src="docs/screenshots/web/W02-staff-sign-in/01-sign-in.png" width="420" alt="W02-staff-sign-in 01-sign-in" title="01-sign-in">
</p>

</details>

<details open>
<summary><b>W03 · Expert console</b> — 6 screens</summary>

*Expert console: Sea Signal and ribbon, ledger open, H2 row draws the border buffer, citations drawer · Agent drives the map*

<p>
<img src="docs/screenshots/web/W03-expert/01-sea-signal.png" width="420" alt="W03-expert 01-sea-signal" title="01-sea-signal">
<img src="docs/screenshots/web/W03-expert/02-ledger.png" width="420" alt="W03-expert 02-ledger" title="02-ledger">
<img src="docs/screenshots/web/W03-expert/03-h2-buffer.png" width="420" alt="W03-expert 03-h2-buffer" title="03-h2-buffer">
<img src="docs/screenshots/web/W03-expert/05-fly-to.png" width="420" alt="W03-expert 05-fly-to" title="05-fly-to">
<img src="docs/screenshots/web/W03-expert/06-mission-control.png" width="420" alt="W03-expert 06-mission-control" title="06-mission-control">
<img src="docs/screenshots/web/W03-expert/07-drag-departure.png" width="420" alt="W03-expert 07-drag-departure" title="07-drag-departure">
</p>

</details>

<details>
<summary><b>W04 · Analyst tools</b> — 0 screens</summary>

*Analyst: anomaly charts, PFZ-vs-INCOIS overlap, CSV/NetCDF downloads, knowledge-base browser*

_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._

</details>

<details>
<summary><b>W05 · District officer</b> — 0 screens</summary>

*Officer: warning areas, anonymised boats, broadcast from approved templates, approval, delivery per language*

_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._

</details>

<details>
<summary><b>W06 · Admin console</b> — 0 screens</summary>

*Admin: overview, data sources, knowledge base and quarantine, supersede, alerts, AI usage, kill switches · Admin: guardrail review, replay with PDF, users and roles, live map, audit log, system health, languages*

_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._

</details>

<details>
<summary><b>W07 · Family on the web</b> — 0 screens</summary>

*Family on the web*

_Not captured in this build (needs a signed-in test account, or the feature is not built yet)._

</details>

<details>
<summary><b>W08 · Web: right-to-left and zoom</b> — 2 screens</summary>

*Web in a right-to-left language and at 200 % zoom*

<p>
<img src="docs/screenshots/web/W08-accessibility/01-rtl.png" width="420" alt="W08-accessibility 01-rtl" title="01-rtl">
<img src="docs/screenshots/web/W08-accessibility/02-zoom-200.png" width="420" alt="W08-accessibility 02-zoom-200" title="02-zoom-200">
</p>

</details>

<details>
<summary><b>R01 · Release build on the live environment</b> — 3 screens</summary>

*Release build against Tier 1: Today, Map, Alerts*

<p>
<img src="docs/screenshots/android/R01-release-smoke/01-today.png" width="200" alt="R01-release-smoke 01-today" title="01-today">
<img src="docs/screenshots/android/R01-release-smoke/02-map.png" width="200" alt="R01-release-smoke 02-map" title="02-map">
<img src="docs/screenshots/android/R01-release-smoke/03-alerts.png" width="200" alt="R01-release-smoke 03-alerts" title="03-alerts">
</p>

</details>


## ⚙ How it works

```mermaid
flowchart LR
    subgraph Phone["📱 Kadal Mitra (Android + Web, one Expo codebase)"]
        UI["Verdict card · Map · Trip · Alerts"]
        BG["Background border watch<br/>(on-device, offline)"]
    end
    UI -->|ask / tap| CK["ty-copilot<br/>CopilotKit runtime"]
    CK --> AG["ty-agent<br/>LangGraph planner + 8 specialists"]
    AG -->|MCP tools| MCP["ty-mcp<br/>data tools · Yukti engine · RAG"]
    MCP --> SRC[("Open-Meteo · INCOIS · IMD/NDMA CAP<br/>NOAA · Copernicus · GFW")]
    MCP --> KB[("Supabase Postgres<br/>pgvector · PostGIS · RLS")]
    AG --> VAL{"Validator<br/>numbers · quotes · language"}
    VAL -->|approved phrases| UI
    MCP --> LEDGER[("Neo4j<br/>evidence ledger")]
    UI <-->|voice, push, positions| CH["ty-channels<br/>Sarvam STT/TTS · push · trips"]
    WK["ty-worker<br/>morning brief · alerts · ingest"] --> CH
```

1. **Gather facts** — forecasts, official warnings, sea temperature, chlorophyll, fishing zones and the border / park
   layers, each with its source and fetch time (cached by H3 cell, never by a person).
2. **Decide** — the Yukti engine tries departure times every 30 minutes over 24 hours, searches the safest route on
   H3 cells, and checks every hard rule (official warnings, border distance, marine park, fishing ban, waves, wind,
   thunderstorms, data freshness). Any failed hard rule means *Don't go*.
3. **Explain** — the agent explains the decision in plain words; document answers quote the source verbatim.
4. **Check** — the validator removes any ungrounded number, fake citation or wrong-language text, then the reply is
   assembled from approved phrases in the user's language.

## 🧭 Who uses it

| | Simple mode (default) | Expert & staff (web) |
|---|---|---|
| **Fisher** | Verdict card, four big buttons, voice, morning brief, trip mode, border alerts | — |
| **Family** | Shared boat card, "back at harbour" notice | — |
| **Expert on the shore** | — | Sea Signal, full rule ledger, citations, map the assistant can drive, departure slider |
| **Scientist** | — | Temperature anomalies, fishing-zone comparison with INCOIS, CSV / NetCDF downloads, document library |
| **Administrator** | — | Data sources, knowledge base, alerts, guardrail review, answer replay, users, audit chain, kill switches |

## 🧱 Built with

| Layer | Stack |
|---|---|
| App | Expo SDK 57 · React Native 0.86 · Expo Router · MapLibre (native + web) · TanStack Query · Zod · i18next |
| AI | LangGraph + LangChain · Gemini 3.8 Flash · Gemini Embedding 2 · FastMCP tools · CopilotKit (AG-UI) |
| Reasoning | Yukti constraint engine (Python) · time-expanded A* on H3 · hybrid RAG (pgvector + full-text, RRF) |
| Voice & language | Sarvam Saaras v4 (speech-to-text), Bulbul v3 (speech), Sarvam-Translate · Noto fonts for every script |
| Data | Supabase (Postgres 17, PostGIS, pgvector, Auth, Storage, row-level security) · Neo4j · Redis |
| Cloud | Azure Container Apps (Central India) · Bicep · Key Vault · Front Door + WAF ready · Application Insights |
| Quality | pytest · Hypothesis · Jest · Playwright · Maestro · promptfoo · TraceRoot · Ruff · mypy --strict · Trivy |

## 📊 Measured, not claimed

| What | Result | Where |
|---|---|---|
| Document search, 440 questions in 22 languages + code-mixed | mean recall@8 **0.925** (gate 0.9; most misses are one document not yet indexed) | [eval report](docs/eval-report.md) |
| Agent safety checks, 86 traced runs in every language | **1.00** on footer, no "safe", no repaired drafts, no figures for unanswerable questions | [improvement report](docs/improvement/report.md) |
| Same language in → same language out (promptfoo) | 24 / 25 languages (Sindhi script decision pending) | [improvement report](docs/improvement/report.md) |
| Phone vs server border distance | within **50 m** wherever alerts happen | `apps/app/__tests__/fences.test.ts` |
| Walkthrough capture (Android emulator + Chrome) | **22 / 22** Android flows and 6 / 6 runnable web flows pass; 51 screens below | [`apps/app/e2e/`](apps/app/e2e) |
| Automated tests | ~400 across Python, Jest, Playwright and the failures dataset; 8 CI jobs | [test report](docs/test-report.md) |

## 🚀 Run it yourself

**Try it now:** the [web app](https://ty-web.wittybay-bae06624.centralindia.azurecontainerapps.io) (demo tier — it
sleeps when idle, so the first load takes ~30 s) or the Android APK from the [releases](https://github.com/Gurjas2112/TarangYukti/releases).

**On your laptop** (Windows Git Bash or WSL; Python 3.12 with `uv`, Node 24 with `pnpm`):

```bash
git clone https://github.com/Gurjas2112/TarangYukti && cd TarangYukti
cp .env.example .env              # add your keys: Supabase, Gemini, Sarvam, Neo4j (see .env.example)
make install                      # pnpm + uv for every service
make infra-up                     # Redis + Grafana (Docker)
make dev                          # agent :8123 · data tools :8001 · channels :8002 · worker · copilot :8200 · app :8081
```

| Command | What it does |
|---|---|
| `make test` · `make lint` · `make typecheck` | Every test, linter and type check (what CI runs) |
| `make demo DATE=YYYY-MM-DD` | Demo from a dated snapshot — works offline |
| `make brief-now USER=<id>` | Send one fisher's morning brief now |
| `make sim-boat POST=1` | Replay a boat trip (border alerts, trip open/close, family notice) |
| `make eval-rag` · `make trace-evals` | Retrieval evaluation · agent evaluation traced into TraceRoot |
| `make capture CAP=… LIVE=…` | Full walkthrough capture: every flow, every language, screenshots + recording |
| `cd apps/app && pnpm start` | The app (Android development build or `pnpm web`) |

Deploying to Azure: [docs/go-live.md](docs/go-live.md).

## 🗂 Repository

```
apps/app        Kadal Mitra — Expo app for Android + web (Simple, Expert, admin)
apps/agent      LangGraph agent: planner, specialists, validator, AG-UI server
services/mcp    FastMCP data tools, Yukti constraint engine, safest route, RAG
services/channels  voice, push, positions, trips, onboarding, admin and provenance API
services/worker    morning brief, alert watch, push outbox, ingestion, housekeeping
services/copilot   CopilotKit runtime between the app and the agent
packages/ty-common shared settings, auth, two-tier cache, telemetry, capture scenarios
config/         rules (constraints.yaml), boats, sources, languages, approved phrases (23 files)
infra/          Docker Compose for the laptop, Bicep for Azure
video/          Remotion story video built from the real walkthrough capture
docs/           specification, reports, runbooks, governance
```

## 🛡 Safety, privacy and honesty

- Personal data stays in Supabase under row-level security; caches and traces never hold phones, names or coordinates.
- Safety wording comes only from phrase files signed by two native speakers. **Every language is still a draft** —
  machine-drafted and waiting for its reviewers — so production shows none of them yet.
- Every failure found becomes a permanent test ([`tests/failures/failures.yaml`](tests/failures/failures.yaml)).
- Not built yet: the district officer's console, and a detailed offline street basemap (the offline map shows the
  coastline, border line and marine park).

## 📚 Learn more

[Engineering specification](docs/TarangYukti_Engineering_Specification_v2.2.md) ·
[Build contract (AGENTS.md)](AGENTS.md) · [Go-live](docs/go-live.md) · [Incident runbook](docs/incident-runbook.md) ·
[DPIA](docs/dpia.md) · [Governance](docs/governance.md) · [Releases](docs/releases.md) ·
[Third-party notices](THIRD_PARTY.md)

<div align="center">

Made with 🌊 for the fishers of the Gulf of Mannar and Palk Bay · MIT licence

</div>
