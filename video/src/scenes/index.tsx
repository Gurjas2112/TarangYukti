// Scene types (spec Table 17-13). App scenes use only the real walkthrough capture; illustrations and diagrams are
// simple SVG drawings (no stock footage); a screen the capture lacks is shown as "not captured", never mocked up.
import { Video } from "@remotion/media";
import type { ReactNode } from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

import { BrowserFrame, CaptionBar, colors, NotCaptured, PhoneFrame, TapRipple } from "../components";
import type { SceneProps } from "../types";

function Stage({ children, scene, family }: { children: ReactNode } & Pick<SceneProps, "scene" | "family">) {
  return (
    <AbsoluteFill style={{ background: colors.deep, alignItems: "center", justifyContent: "center" }}>
      {children}
      <CaptionBar text={scene.text} rtl={scene.rtl} family={family} />
    </AbsoluteFill>
  );
}

function useShot(scene: SceneProps["scene"]) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });
  const tap = scene.taps[0];
  const tapFrame = tap ? Math.round(tap.at * fps) : Number.MAX_SAFE_INTEGER;
  const zoom = tap
    ? interpolate(frame, [tapFrame - fps, tapFrame], [1, 1.12], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 1;
  // more than one shot: step through them evenly, switching half a second after a tap when there is one
  const per = (scene.seconds * fps) / Math.max(1, scene.shots.length);
  const idx = tap && scene.shots.length === 2 ? (frame < tapFrame + fps / 2 ? 0 : 1) : Math.min(scene.shots.length - 1, Math.floor(frame / per));
  return { enter, zoom, tap, tapFrame, shot: scene.shots[idx] };
}

export function PhoneShots({ scene, layout, family }: SceneProps) {
  const { enter, zoom, tap, tapFrame, shot } = useShot(scene);
  return (
    <Stage scene={scene} family={family}>
      <PhoneFrame layout={layout} style={{ transform: `translateY(${(1 - enter) * 80}px) scale(${zoom})` }}>
        {shot ? <Img src={staticFile(shot)} style={{ width: "100%" }} /> : <NotCaptured names={scene.missing} family={family} />}
        {tap && shot ? <TapRipple x={tap.x} y={tap.y} startFrame={tapFrame} /> : null}
      </PhoneFrame>
    </Stage>
  );
}

export function BrowserShots({ scene, layout, family }: SceneProps) {
  const { enter, zoom, shot } = useShot(scene);
  return (
    <Stage scene={scene} family={family}>
      <BrowserFrame layout={layout} style={{ transform: `translateY(${(1 - enter) * 60}px) scale(${zoom})` }}>
        {shot ? (
          <Img src={staticFile(shot)} style={{ width: "100%", display: "block" }} />
        ) : (
          <div style={{ height: 600, position: "relative" }}>
            <NotCaptured names={scene.missing} family={family} />
          </div>
        )}
      </BrowserFrame>
    </Stage>
  );
}

export function PhoneClip({ scene, layout, family }: SceneProps) {
  return (
    <Stage scene={scene} family={family}>
      <PhoneFrame layout={layout}>
        {scene.clip ? (
          <Video src={staticFile(scene.clip)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <NotCaptured names={scene.missing} family={family} />
        )}
      </PhoneFrame>
    </Stage>
  );
}

export function BrowserClip({ scene, layout, family }: SceneProps) {
  return (
    <Stage scene={scene} family={family}>
      <BrowserFrame layout={layout}>
        {scene.clip ? (
          <Video src={staticFile(scene.clip)} muted style={{ width: "100%", display: "block" }} />
        ) : (
          <div style={{ height: 600, position: "relative" }}>
            <NotCaptured names={scene.missing} family={family} />
          </div>
        )}
      </BrowserFrame>
    </Stage>
  );
}

// ── context illustrations (drawn, fictional, no real people) ──────────────────────────────────────────────

function Sea({ children }: { children?: ReactNode }) {
  const frame = useCurrentFrame();
  const sway = Math.sin(frame / 18) * 6;
  return (
    <svg viewBox="0 0 1600 900" style={{ width: "86%", height: "auto" }}>
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1B2F4A" />
          <stop offset="1" stopColor="#F3A867" />
        </linearGradient>
      </defs>
      <rect width="1600" height="520" fill="url(#sky)" />
      <circle cx="1180" cy="520" r="90" fill="#FFD27A" />
      <rect y="500" width="1600" height="400" fill="#2B6B8F" />
      {[0, 1, 2, 3].map((i) => (
        <path key={i} d={`M0 ${560 + i * 70 + sway} Q400 ${540 + i * 70 - sway} 800 ${560 + i * 70 + sway} T1600 ${560 + i * 70}`} stroke="#9CC9E0" strokeWidth="3" fill="none" opacity="0.5" />
      ))}
      {children}
    </svg>
  );
}

function Boat({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <path d="M-120 0 L120 0 L80 50 L-80 50 Z" fill="#E8E2D2" stroke="#3A2E1E" strokeWidth="4" />
      <rect x="-6" y="-150" width="10" height="150" fill="#3A2E1E" />
      <path d="M4 -140 L90 -20 L4 -20 Z" fill="#F7F3E8" stroke="#3A2E1E" strokeWidth="3" />
      <circle cx="-50" cy="-36" r="16" fill="#6B4A2F" />
      <rect x="-64" y="-20" width="28" height="22" fill="#2F6FDE" />
    </g>
  );
}

const ART: Record<string, () => ReactNode> = {
  "dawn-harbour": () => (
    <Sea>
      <rect x="0" y="470" width="420" height="60" fill="#5B4A36" />
      <Boat x={640} y={560} />
    </Sea>
  ),
  bulletins: () => (
    <Sea>
      {[0, 1, 2, 3, 4].map((i) => (
        <g key={i} transform={`translate(${260 + i * 230} ${180 + (i % 2) * 90}) rotate(${(i - 2) * 6})`}>
          <rect width="180" height="230" fill="#FFFFFF" stroke="#999" />
          {[0, 1, 2, 3, 4, 5].map((l) => (
            <rect key={l} x="20" y={30 + l * 30} width={140 - (l % 3) * 30} height="10" fill="#BBB" />
          ))}
        </g>
      ))}
    </Sea>
  ),
  border: () => (
    <Sea>
      <path d="M980 500 L1080 900" stroke={colors.noGo} strokeWidth="8" strokeDasharray="28 18" />
      <Boat x={700} y={620} />
    </Sea>
  ),
  family: () => (
    <svg viewBox="0 0 1600 900" style={{ width: "86%" }}>
      <rect width="1600" height="900" fill="#F4EBDD" />
      <rect x="240" y="300" width="520" height="420" fill="#D9C7AA" />
      <polygon points="200,300 500,120 800,300" fill="#9C6B43" />
      <rect x="980" y="260" width="300" height="560" rx="40" fill="#111" />
      <rect x="1000" y="290" width="260" height="500" rx="24" fill="#FFFFFF" />
      <circle cx="1130" cy="460" r="60" fill={colors.go} />
      <path d="M1100 460 l22 22 l40 -44" stroke="#FFF" strokeWidth="12" fill="none" />
    </svg>
  ),
};

export function Illustration({ scene, family }: SceneProps) {
  const draw = ART[scene.art ?? "dawn-harbour"] ?? ART["dawn-harbour"];
  return (
    <Stage scene={scene} family={family}>
      {draw()}
    </Stage>
  );
}

/** Animated diagram: labelled steps appearing one after another, read from `label` ("A → B → C"). */
export function Diagram({ scene, family }: SceneProps) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const steps = (scene.label ?? "").split("→").map((s) => s.trim()).filter(Boolean);
  return (
    <Stage scene={scene} family={family}>
      <div style={{ display: "flex", alignItems: "center", gap: 28, padding: 60, flexWrap: "wrap", justifyContent: "center", marginBottom: 160 }}>
        {steps.map((s, i) => {
          const show = spring({ frame: frame - i * fps * 0.8, fps, config: { damping: 200 } });
          return (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: 28, opacity: show, transform: `translateY(${(1 - show) * 30}px)` }}>
              <div style={{ background: i === steps.length - 1 ? colors.go : "#17324F", color: colors.white, fontFamily: family, fontSize: 36, fontWeight: 700, padding: "26px 34px", borderRadius: 18, maxWidth: 420, textAlign: "center" }}>
                {s}
              </div>
              {i < steps.length - 1 ? <div style={{ color: colors.isro, fontSize: 56 }}>→</div> : null}
            </div>
          );
        })}
      </div>
    </Stage>
  );
}

export function Title({ scene, family }: SceneProps) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill style={{ background: colors.deep, alignItems: "center", justifyContent: "center", fontFamily: family, color: colors.white }}>
      <div style={{ fontSize: 110, fontWeight: 700, opacity: enter }}>{scene.label ?? "Kadal Mitra"}</div>
      <div dir={scene.rtl ? "rtl" : "ltr"} style={{ fontSize: 40, marginTop: 30, maxWidth: 1400, textAlign: "center", opacity: interpolate(frame, [fps, fps * 2], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        {scene.text}
      </div>
    </AbsoluteFill>
  );
}

export const SCENES = {
  illustration: Illustration,
  "phone-shots": PhoneShots,
  "phone-clip": PhoneClip,
  "browser-shots": BrowserShots,
  "browser-clip": BrowserClip,
  diagram: Diagram,
  title: Title,
} as const;
