// Analyst tools (spec §7.5, §11): SST anomaly chart with the heatwave test, computed-zones overlap with INCOIS,
// CSV / NetCDF downloads and the knowledge-base browser. Web only (Recharts).
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { expertApi, useAnomaly, usePfz } from "../api/expert";
import { colors } from "../ui/tokens";

const box: React.CSSProperties = { border: `1px solid ${colors.border}`, borderRadius: 8, padding: 12, background: "#fff" };
const h: React.CSSProperties = { fontSize: 16, fontWeight: 700, margin: "0 0 8px" };
const small: React.CSSProperties = { fontSize: 13, color: colors.textMuted };

export function AnalystPanel({ lat, lon }: { lat: number; lon: number }) {
  const { t } = useTranslation();
  const anomaly = useAnomaly(lat, lon);
  const pfz = usePfz();
  const docs = useQuery({ queryKey: ["kb-docs"], queryFn: expertApi.documents, staleTime: 600_000 });
  const series = anomaly.data?.data.series ?? [];
  const hw = anomaly.data?.data.heatwave;
  const comp = pfz.data?.computed.data;

  async function netcdf(kind: "sst" | "chl") {
    const r = await expertApi.netcdf(kind);
    window.open(r.url, "_blank", "noopener");
  }

  return (
    <div data-testid="analyst-panel" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12 }}>
      <section style={box} data-testid="anomaly-chart">
        <h3 style={h}>{t("analyst.anomaly")}</h3>
        {anomaly.isLoading ? <p style={small}>…</p> : null}
        {anomaly.data?.data.available === false ? <p style={small}>{anomaly.data.data.reason}</p> : null}
        {series.length ? (
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ left: -16, right: 8, top: 4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#ddd" />
                <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} fontSize={11} />
                <YAxis fontSize={11} unit="°C" />
                <Tooltip />
                {hw?.threshold_c !== undefined ? <ReferenceLine y={hw.threshold_c} stroke={colors.caution} strokeDasharray="4 2" /> : null}
                <Line isAnimationActive={false} type="monotone" dataKey="anom_c" stroke={colors.noGo} dot={false} strokeWidth={2} name={t("analyst.anomalyLine")} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : null}
        {hw?.tested ? (
          <p style={small} data-testid="heatwave">
            {t("analyst.meanAnomaly")} {hw.mean_anom_c} °C · {hw.heatwave ? t("analyst.heatwaveYes") : t("analyst.heatwaveNo")} ·{" "}
            {anomaly.data?.source}
          </p>
        ) : null}
      </section>

      <section style={box} data-testid="pfz-overlap">
        <h3 style={h}>{t("analyst.zones")}</h3>
        {pfz.isLoading ? <p style={small}>…</p> : null}
        {comp?.available === false ? <p style={small}>{comp.reason}</p> : null}
        {comp?.zones ? (
          <>
            <p style={{ fontSize: 15, margin: 0 }}>
              {t("analyst.zoneCount", { n: comp.zones.length })} · {t("analyst.frontCells", { n: comp.front_cells ?? 0 })}
            </p>
            <p style={{ fontSize: 15, margin: "4px 0" }} data-testid="overlap-score">
              {t("analyst.overlap")}:{" "}
              {comp.overlap_incois === null || comp.overlap_incois === undefined
                ? t("analyst.noIncois")
                : `${Math.round(comp.overlap_incois * 100)}% (${comp.incois_points} ${t("analyst.points")})`}
            </p>
            <p style={small}>{pfz.data?.computed.notes.join(" · ")}</p>
            <p style={small}>{t("analyst.zonesCaveat")}</p>
          </>
        ) : null}
      </section>

      <section style={box} data-testid="downloads">
        <h3 style={h}>{t("analyst.downloads")}</h3>
        {(["sst", "chl"] as const).map((k) => (
          <p key={k} style={{ margin: "4px 0", fontSize: 15 }}>
            {t(`analyst.${k}`)}:{" "}
            <a href={expertApi.csvUrl(k)} data-testid={`csv-${k}`}>
              CSV
            </a>{" "}
            ·{" "}
            <a href="#" onClick={(e) => (e.preventDefault(), void netcdf(k))} data-testid={`netcdf-${k}`}>
              NetCDF ({t("analyst.fromSource")})
            </a>
          </p>
        ))}
      </section>

      <section style={{ ...box, gridColumn: "1 / -1" }} data-testid="kb-browser">
        <h3 style={h}>{t("analyst.kb")}</h3>
        <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left" }}>
              <th>{t("analyst.issuer")}</th>
              <th>{t("analyst.document")}</th>
              <th>{t("analyst.status")}</th>
              <th>{t("expert.validTill")}</th>
              <th>{t("analyst.chunks")}</th>
            </tr>
          </thead>
          <tbody>
            {(docs.data ?? []).map((d) => (
              <tr key={d.id} style={{ borderTop: "1px solid #eee" }}>
                <td>{d.issuer}</td>
                <td>{d.url ? <a href={d.url} target="_blank" rel="noopener noreferrer">{d.source_id}</a> : d.source_id}</td>
                <td>{d.status}</td>
                <td>{d.valid_to?.slice(0, 10) ?? "—"}</td>
                <td>{d.chunks}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
