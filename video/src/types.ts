// Timeline written by scripts/build_assets.py for one language (public/timeline.<code>.json).
export type Tap = { x: number; y: number; at: number };

export type SceneKind = "illustration" | "phone-shots" | "phone-clip" | "browser-shots" | "browser-clip" | "diagram" | "title";

export type Scene = {
  id: string;
  chapter: number;
  kind: SceneKind;
  text: string;
  narration: string | null;
  covers: string[];
  seconds: number;
  taps: Tap[];
  shots: string[];
  clip?: string;
  /** Screens named in the script that this capture does not have yet: shown as a labelled card, never invented. */
  missing: string[];
  art?: string;
  label?: string;
  rtl: boolean;
};

export type Timeline = {
  lang: string;
  rtl: boolean;
  font: { regular: string; bold: string; family: string } | null;
  chapters: Record<string, string>;
  scenes: Scene[];
};

export type Layout = "landscape" | "portrait";

export type StoryProps = { lang: string; layout: Layout; timeline?: Timeline };

export type SceneProps = { scene: Scene; layout: Layout; family: string };
