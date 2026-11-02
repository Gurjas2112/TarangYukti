import { describe, expect, it } from "@jest/globals";
import { render, screen } from "@testing-library/react-native";

import { parseEnv } from "../src/env";
import { nearestLanguage, t } from "../src/i18n";
import { HomeScreen } from "../src/screens/HomeScreen";
import { colors, contrast, MIN_CONTRAST } from "../src/ui/tokens";

describe("sunlight theme", () => {
  it("text on background meets 7:1", () => {
    expect(contrast(colors.text, colors.background)).toBeGreaterThanOrEqual(MIN_CONTRAST);
    expect(contrast(colors.textMuted, colors.background)).toBeGreaterThanOrEqual(MIN_CONTRAST);
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

describe("language", () => {
  it("picks the nearest available catalogue", () => {
    expect(nearestLanguage(["ta-IN", "en-GB"], ["en-IN", "ta-IN"])).toBe("ta-IN");
    expect(nearestLanguage(["en-GB"], ["ml-IN", "en-IN"])).toBe("en-IN");
  });
  it("falls back to the key when missing", () => {
    expect(t("no.such.key", "en-IN")).toBe("no.such.key");
  });
});

describe("HomeScreen", () => {
  it("renders the advisory footer", async () => {
    await render(<HomeScreen lang="en-IN" />);
    expect(screen.getByText("Advisory only — follow official INCOIS/IMD warnings.")).toBeTruthy();
    expect(screen.getByTestId("home-not-ready")).toBeTruthy();
  });
});
