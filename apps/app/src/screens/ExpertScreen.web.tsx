// Expert console (spec §7.10, Figure 7-4): the map with layers on the left; the copilot, Sea Signal, Constraint
// Ledger (open by default) and citations on the right; Mission Control, the departure slider and analyst tools
// along the bottom. Codes (PFZ, IMBL, H1–H8) appear here and only here.
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, type BoatKind } from "../api/channels";
import { base, type LedgerEntry, useGrid, usePfz, usePlan } from "../api/expert";
import { AnalystPanel } from "../components/AnalystPanel.web";
import { type CitationCard, CitationChip, CitationDrawer } from "../components/CitationChip";
import { ConstraintLedger } from "../components/ConstraintLedger";
import { DepartSlider } from "../components/DepartSlider.web";
import { LanguageButton } from "../components/LanguagePicker";
import { MissionControl } from "../components/MissionControl";
import { SeaSignal } from "../components/SeaSignal";
import { type AgentTurn, useAsk } from "../copilot/useAsk";
import { runUiActions, useExpertTools, useSeaTools } from "../copilot/useSeaTools";
import { OceanMap } from "../map/OceanMap.web";
import { mapRef } from "../map/ref";
import { ALL_LAYERS, type LayerId, type PfzZone } from "../map/types";
import { usePrefs } from "../state/prefs";
import { colors } from "../ui/tokens";

const STEPS = 48; // 24 h in 30-minute steps
const BOATS: BoatKind[] = ["non_motorised", "small_frp", "mechanised_trawler"];
const ist = (d: Date) =>
  d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });

type Turn = { q: string; a: AgentTurn };

export function ExpertScreen() {
  const { t } = useTranslation();
  const { prefs, update } = usePrefs();
  const harbours = useQuery({ queryKey: ["harbours"], queryFn: api.harbours });
  const harbour = prefs.harbour ?? harbours.data?.[0]?.id ?? null;
  const [boat, setBoat] = useState<BoatKind>(prefs.boatKind ?? "small_frp");
  const [step, setStep] = useState(0);
  const [t0] = useState(() => {
    const d = new Date();
    d.setUTCMinutes(d.getUTCMinutes() < 30 ? 30 : 60, 0, 0); // next half hour
    return d.getTime();
  });
  const departAt = step === 0 ? null : new Date(t0 + (step - 1) * 30 * 60_000).toISOString();
  const departLabel = step === 0 ? t("expert.now") : ist(new Date(t0 + (step - 1) * 30 * 60_000));

  const plan = usePlan(harbour ?? "", boat, departAt);
  const [layers, setLayers] = useState<LayerId[]>(["land", "imbl", "mpa", "sst", "pfz", "incois", "route"]);
  const sst = useGrid("sst", layers.includes("sst"));
  const chl = useGrid("chl", layers.includes("chl"));
  const pfz = usePfz(layers.includes("pfz") || layers.includes("incois"));

  const [ledgerOpen, setLedgerOpen] = useState(true);
  const [showHow, setShowHow] = useState(true);
  const [analyst, setAnalyst] = useState(false);
  const [citation, setCitation] = useState<CitationCard | null>(null);
  const { ask, busy } = useAsk();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const ledgerAnchor = useRef<HTMLDivElement | null>(null);

  const handlers = {
    openLedger: () => {
      setLedgerOpen(true);
      ledgerAnchor.current?.scrollIntoView({ behavior: "smooth" });
    },
    openWhy: () => setLedgerOpen(true),
    openCitation: (chunkId: number) =>
      setCitation({ marker: "K", quote: "", chunk_id: chunkId, issuer: null, title: null, valid_to: null }),
    setDepart: (iso: string) => {
      const s = Math.round((new Date(iso).getTime() - t0) / 1_800_000) + 1;
      setStep(Math.min(STEPS, Math.max(0, s)));
    },
  };
  useSeaTools(handlers);
  useExpertTools(handlers);

  const d = plan.data?.data;
  const h2Limit = d?.limits.H2?.value;
  const mapData = useMemo(
    () => ({
      sst: sst.data?.data.points,
      chl: chl.data?.data.points,
      pfz: (pfz.data?.computed.data.zones ?? []) as PfzZone[],
      incois: pfz.data?.incois.data.zones ?? [],
      route: (d?.requested.route as GeoJSON.LineString | null | undefined) ?? null,
      harbour: d ? { lat: d.harbour.lat, lon: d.harbour.lon, name: d.harbour.name } : undefined,
      imblBufferKm: h2Limit,
    }),
    [sst.data, chl.data, pfz.data, d, h2Limit],
  );

  // this screen is Expert mode: the agent answers with codes, figures and the ledger (prefs feed the provider)
  useEffect(() => {
    if (prefs.mode !== "expert") void update({ mode: "expert" });
  }, [prefs.mode, update]);

  useEffect(() => {
    if (d) mapRef.current?.flyTo(d.harbour.lon, d.harbour.lat, 8.5);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d?.harbour.id]);

  function onRow(e: LedgerEntry) {
    if (e.id === "H2") mapRef.current?.showLayer("imblBuffer", true); // draw the border buffer
    if (e.id === "H5" || e.id === "H6") mapRef.current?.showLayer("route", true);
  }

  async function send(q: string) {
    if (!q.trim()) return;
    setDraft("");
    const a = await ask(q);
    setTurns((x) => [...x, { q, a }]);
    runUiActions(a.uiActions, handlers);
  }

  const lastMission = turns.at(-1)?.a.mission ?? [];
  const suggestions = [t("expert.ask.tomorrow"), t("expert.ask.border"), t("expert.ask.law")];

  return (
    <div style={{ position: "fixed", inset: 0, display: "flex", flexDirection: "column", background: colors.foam, fontFamily: "system-ui, 'Noto Sans', sans-serif" }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center", padding: "8px 16px", background: colors.deep, color: "#fff", flexWrap: "wrap" }}>
        <strong style={{ fontSize: 18 }}>TarangYukti</strong>
        <select
          aria-label={t("me.harbour")}
          data-testid="expert-harbour"
          value={harbour ?? ""}
          onChange={(e) => void update({ harbour: e.target.value })}
        >
          {(harbours.data ?? []).map((h) => (
            <option key={h.id} value={h.id}>
              {h.name}
            </option>
          ))}
        </select>
        <select aria-label={t("me.boat")} data-testid="expert-boat" value={boat} onChange={(e) => setBoat(e.target.value as BoatKind)}>
          {BOATS.map((b) => (
            <option key={b} value={b}>
              {t(`onboarding.boat.${b}`)}
            </option>
          ))}
        </select>
        <div style={{ background: "#fff", borderRadius: 6 }}>
          <LanguageButton />
        </div>
        <button
          data-testid="switch-simple"
          onClick={() => {
            router.replace("/");
            void update({ mode: "simple" });
          }}
        >
          {t("me.mode.simple")}
        </button>
        <span style={{ marginLeft: "auto", fontSize: 13 }} data-testid="data-freshness">
          {plan.data ? `${t("expert.data")}: ${plan.data.confidence} · ${plan.data.cache}` : plan.isError ? t("expert.planError") : "…"}
        </span>
      </header>

      <main style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <section style={{ flex: 1, position: "relative", minWidth: 0 }}>
          <OceanMap
            ref={(h) => {
              mapRef.current = h;
            }}
            initialCenter={{ lon: 79.2, lat: 9.25 }}
            initialZoom={7.6}
            layers={layers}
            data={mapData}
            layerBaseUrl={base()}
            onLayersChange={setLayers}
            testID="ocean-map"
          />
          <fieldset data-testid="layer-toggles" style={{ position: "absolute", zIndex: 2, right: 8, top: 8, background: "#ffffffee", border: "1px solid #999", borderRadius: 6, fontSize: 13, padding: 8 }}>
            <legend>{t("expert.layers")}</legend>
            {ALL_LAYERS.map((id) => (
              <label key={id} style={{ display: "block" }}>
                <input
                  type="checkbox"
                  data-testid={`layer-${id}`}
                  checked={layers.includes(id)}
                  onChange={(e) => setLayers((v) => (e.target.checked ? [...v, id] : v.filter((x) => x !== id)))}
                />{" "}
                {t(`layers.${id}`)}
              </label>
            ))}
          </fieldset>
        </section>

        <aside style={{ width: 440, overflowY: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 12, borderLeft: "1px solid #ccc", background: "#fff" }}>
          <div data-testid="copilot-panel" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <strong>{t("expert.copilot")}</strong>
            {turns.map((x, i) => (
              <div key={i} style={{ fontSize: 14, borderBottom: "1px solid #eee", paddingBottom: 6 }}>
                <div style={{ color: colors.textMuted }}>› {x.q}</div>
                <div data-testid="expert-reply" style={{ whiteSpace: "pre-wrap" }}>{x.a.reply}</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                  {x.a.citations.map((c) => (
                    <CitationChip key={c.marker} c={c} onOpen={setCitation} />
                  ))}
                </div>
              </div>
            ))}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {suggestions.map((s, i) => (
                <button key={s} data-testid={`suggest-${i}`} disabled={busy} onClick={() => void send(s)}>
                  {s}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void send(draft);
              }}
              style={{ display: "flex", gap: 6 }}
            >
              <input
                data-testid="expert-input"
                aria-label={t("expert.askLabel")}
                value={draft}
                maxLength={2000}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={t("expert.askLabel")}
                style={{ flex: 1, fontSize: 15, padding: 6 }}
              />
              <button type="submit" disabled={busy} data-testid="expert-send">
                {busy ? "…" : t("expert.send")}
              </button>
            </form>
          </div>

          {plan.data ? <SeaSignal plan={plan.data} /> : null}
          {plan.isError ? <p data-testid="plan-error">{t("expert.planError")}</p> : null}

          <div ref={ledgerAnchor}>
            <button data-testid="ledger-toggle" onClick={() => setLedgerOpen((o) => !o)}>
              {ledgerOpen ? "▾" : "▸"} {t("expert.ledger")}
            </button>
            {ledgerOpen && d ? <ConstraintLedger entries={d.requested.ledger} limits={d.limits} onRow={onRow} /> : null}
          </div>
          <p style={{ fontSize: 13, color: colors.textMuted }}>{t("footerExpert")}</p>
        </aside>
      </main>

      <footer style={{ padding: "8px 16px", borderTop: "1px solid #ccc", background: "#fff", display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ fontSize: 14 }}>
            <input type="checkbox" data-testid="show-how" checked={showHow} onChange={(e) => setShowHow(e.target.checked)} />{" "}
            {t("expert.showHow")}
          </label>
          {showHow ? <MissionControl steps={lastMission} busy={busy} /> : null}
        </div>
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          <DepartSlider steps={STEPS} value={step} label={departLabel} onChange={setStep} />
          <button data-testid="analyst-toggle" onClick={() => setAnalyst((a) => !a)}>
            {analyst ? "▾" : "▸"} {t("expert.analyst")}
          </button>
        </div>
        {analyst && d ? (
          <div style={{ maxHeight: "45vh", overflowY: "auto" }}>
            <AnalystPanel lat={d.harbour.lat} lon={d.harbour.lon} />
          </div>
        ) : null}
      </footer>
      <CitationDrawer c={citation} onClose={() => setCitation(null)} />
    </div>
  );
}
