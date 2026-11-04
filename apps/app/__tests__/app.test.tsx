import { describe, expect, it, jest } from "@jest/globals";
import { fireEvent, render, screen } from "@testing-library/react-native";

import type { Brief } from "../src/api/channels";
import { FourButtons } from "../src/components/FourButtons";
import { TimeRibbon } from "../src/components/TimeRibbon";
import { VerdictCard } from "../src/components/VerdictCard";
import { parseEnv } from "../src/env";
import { allLanguages, availableLanguages, nearestLanguage } from "../src/i18n";
import { catalogues } from "../src/i18n/catalogues";
import { colors, contrast, MIN_CONTRAST } from "../src/ui/tokens";

const CODES = /\b(PFZ|IMBL|H[1-8]|S[1-5])\b/;

const brief: Brief = {
  harbour: { id: "rameswaram", name: "Rameswaram" },
  boat_type: "small_frp",
  lang: "en-IN",
  as_of: "05:30",
  verdict: "CAUTION",
  headline: "Go, but carefully — back by 09:00.",
  why: ["Waves get too high after 09:00."],
  window: { depart: "05:30", back_by: "09:00", verdict: "CAUTION" },
  ribbon: Array.from({ length: 24 }, (_, i) => ({
    time: `${String(i).padStart(2, "0")}:30`,
    verdict: i < 8 ? ("GO" as const) : i < 16 ? ("CAUTION" as const) : ("NO-GO" as const),
  })),
  spot: { distance_km: 18, text: "Fish likely 18 km south-east." },
  border: { distance_km: 23, text: "Border line is 23 km away." },
  stale: null,
  footer: "Advisory only — follow official INCOIS/IMD warnings.",
  answer_id: null,
  simulation: true,
  sources: ["Open-Meteo Marine"],
  fetched_at: "2026-11-04T00:00:00Z",
  speak: "Go, but carefully — back by 09:00.",
};

describe("sunlight theme", () => {
  it("text and verdict colours meet 7:1 on white", () => {
    for (const c of [colors.text, colors.textMuted, colors.go, colors.caution, colors.noGo]) {
      expect(contrast(c, colors.background)).toBeGreaterThanOrEqual(MIN_CONTRAST);
    }
  });
});

describe("env", () => {
  it("accepts public values and rejects a missing runtime URL", () => {
    const ok = parseEnv({
      EXPO_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
      EXPO_PUBLIC_SUPABASE_ANON_KEY: "sb_publishable_x",
      EXPO_PUBLIC_COPILOT_URL: "http://localhost:8200",
      EXPO_PUBLIC_CHANNELS_URL: "http://localhost:8002",
    });
    expect(ok.COPILOT_URL).toBe("http://localhost:8200");
    expect(() => parseEnv({ EXPO_PUBLIC_SUPABASE_URL: "x" })).toThrow();
  });
});

describe("languages", () => {
  it("lists all 23 languages and has a catalogue for each", () => {
    expect(allLanguages).toHaveLength(23);
    for (const l of allLanguages) expect(catalogues[l.code]).toBeDefined();
  });

  it("every catalogue has every key, with the same {{variables}} (CI key check)", () => {
    const en = catalogues["en-IN"];
    const vars = (s: string) => (s.match(/\{\{\s*\w+\s*\}\}/g) ?? []).sort();
    for (const l of allLanguages) {
      const cat = catalogues[l.code];
      for (const key of Object.keys(en)) {
        expect([l.code, key, typeof cat[key]]).toEqual([l.code, key, "string"]);
        expect([l.code, key, vars(cat[key])]).toEqual([l.code, key, vars(en[key])]);
      }
    }
  });

  it("production builds offer only released languages; staging offers all", () => {
    expect(availableLanguages("production").every((l) => l.status === "released")).toBe(true);
    expect(availableLanguages("development")).toHaveLength(23);
  });

  it("picks the nearest available language without a built-in default", () => {
    expect(nearestLanguage(["ta-IN", "en-GB"], ["en-IN", "ta-IN"])).toBe("ta-IN");
    expect(nearestLanguage(["ml"], ["ml-IN", "en-IN"])).toBe("ml-IN");
    expect(nearestLanguage(["fr-FR"], ["hi-IN", "en-IN"])).toBe("hi-IN");
  });

  it("marks right-to-left scripts", () => {
    const rtl = allLanguages.filter((l) => l.rtl).map((l) => l.code);
    expect(rtl).toEqual(expect.arrayContaining(["ur-IN", "ks-IN"]));
  });
});

describe("Simple mode components", () => {
  it("verdict card shows a word, the headline and the simulation label — no codes", async () => {
    await render(<VerdictCard brief={brief} />);
    expect(screen.getByTestId("verdict-caution")).toBeTruthy();
    expect(screen.getByText(brief.headline)).toBeTruthy();
    expect(screen.getByTestId("verdict-simulation")).toBeTruthy();
    const all = [brief.headline, ...brief.why, brief.border.text, brief.spot!.text, brief.footer].join(" ");
    expect(CODES.test(all)).toBe(false);
  });

  it("ribbon has 24 bars and an accessible summary", async () => {
    await render(<TimeRibbon ribbon={brief.ribbon} />);
    expect(screen.getByTestId("time-ribbon").props.accessibilityLabel).toContain("00:30");
  });

  it("four buttons have stable test ids and report presses", async () => {
    const onPress = jest.fn();
    await render(<FourButtons onPress={onPress} />);
    for (const id of ["today", "fish", "alerts", "back"]) {
      fireEvent.press(screen.getByTestId(`button-${id}`));
    }
    expect(onPress.mock.calls.map((c) => c[0])).toEqual(["today", "fish", "alerts", "back"]);
  });
});
