// Shared pieces of every scene (spec Table 17-13): unbranded phone and browser frames drawn in CSS, a tap
// ripple, call-outs, the caption bar (right-to-left aware), the chapter card and the "not captured yet" card.
import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

import type { Layout } from "../types";

export const colors = {
  deep: "#0B1D2E",
  foam: "#F5F7F6",
  go: "#07612A",
  caution: "#7A4A00",
  noGo: "#A30000",
  action: "#2F6FDE",
  isro: "#F26B21",
  white: "#FFFFFF",
};

export function PhoneFrame({ layout, style, children }: { layout: Layout; style?: CSSProperties; children: ReactNode }) {
  const h = layout === "portrait" ? 1380 : 860;
  return (
    <div
      style={{
        height: h,
        aspectRatio: "9 / 19.5",
        borderRadius: 54,
        background: "#111",
        padding: 16,
        boxShadow: "0 30px 80px rgba(0,0,0,.45)",
        ...style,
      }}
    >
      <div style={{ width: "100%", height: "100%", borderRadius: 40, overflow: "hidden", background: colors.white, position: "relative" }}>
        {children}
      </div>
    </div>
  );
}

export function BrowserFrame({ layout, style, children }: { layout: Layout; style?: CSSProperties; children: ReactNode }) {
  const w = layout === "portrait" ? 1000 : 1600;
  return (
    <div style={{ width: w, borderRadius: 16, background: "#E6E9EC", boxShadow: "0 30px 80px rgba(0,0,0,.4)", ...style }}>
      <div style={{ display: "flex", gap: 10, padding: "14px 18px" }}>
        {["#E26B5B", "#E6B84F", "#69B86B"].map((c) => (
          <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />
        ))}
        <div style={{ flex: 1, height: 16, borderRadius: 8, background: colors.white, marginLeft: 12 }} />
      </div>
      <div style={{ overflow: "hidden", borderRadius: "0 0 16px 16px", background: colors.white, position: "relative" }}>{children}</div>
    </div>
  );
}

export function TapRipple({ x, y, startFrame }: { x: number; y: number; startFrame: number }) {
  const frame = useCurrentFrame();
  const t = frame - startFrame;
  if (t < 0 || t > 24) return null;
  const r = interpolate(t, [0, 24], [10, 70]);
  return (
    <div
      style={{
        position: "absolute",
        left: `${x * 100}%`,
        top: `${y * 100}%`,
        width: r * 2,
        height: r * 2,
        marginLeft: -r,
        marginTop: -r,
        borderRadius: r,
        border: `6px solid ${colors.action}`,
        opacity: interpolate(t, [0, 24], [0.9, 0]),
      }}
    />
  );
}

export function Callout({ text, family }: { text: string; family: string }) {
  return (
    <div style={{ background: colors.isro, color: colors.white, fontFamily: family, fontSize: 30, fontWeight: 700, padding: "10px 22px", borderRadius: 12 }}>
      {text}
    </div>
  );
}

export function CaptionBar({ text, rtl, family }: { text: string; rtl: boolean; family: string }) {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div
      dir={rtl ? "rtl" : "ltr"}
      style={{
        position: "absolute",
        left: 60,
        right: 60,
        bottom: 40,
        padding: "18px 28px",
        borderRadius: 14,
        background: "rgba(11,29,46,.82)",
        color: colors.white,
        fontFamily: family,
        fontSize: 34,
        lineHeight: 1.35,
        textAlign: "center",
        opacity,
      }}
    >
      {text}
    </div>
  );
}

export function ChapterCard({ n, title, family }: { n: number; title: string; family: string }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });
  const out = interpolate(frame, [fps * 1.6, fps * 2.2], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute",
        top: 50,
        left: 60,
        transform: `translateX(${(1 - enter) * -60}px)`,
        opacity: out,
        fontFamily: family,
        color: colors.white,
      }}
    >
      <div style={{ fontSize: 26, letterSpacing: 4, color: colors.isro }}>{String(n).padStart(2, "0")}</div>
      <div style={{ fontSize: 48, fontWeight: 700 }}>{title}</div>
    </div>
  );
}

/** A screen the script names but this capture does not have: said plainly, never mocked up. */
export function NotCaptured({ names, family }: { names: string[]; family: string }) {
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: 40, background: "#EEF2F5" }}>
      <div style={{ fontFamily: family, fontSize: 30, color: "#555", textAlign: "center" }}>
        Screen not captured in this build
        <div style={{ fontSize: 22, marginTop: 12, opacity: 0.7 }}>{names.join(" · ")}</div>
      </div>
    </AbsoluteFill>
  );
}
