// Typed design tokens. Sunlight theme is the default for Simple mode (prompt §10.9):
// white background, black text, contrast ≥ 7:1, verdict ≥ 40 px, body ≥ 18 px, icons always with words.

export const colors = {
  background: "#FFFFFF",
  text: "#000000",
  textMuted: "#333333",
  border: "#1A1A1A",
  go: "#07612A", // 7.6:1 on white
  caution: "#7A4A00",
  noGo: "#A30000",
  link: "#0040A0",
  // Expert mode (spec Table 7-1)
  deep: "#0B1D2E",
  foam: "#F5F7F6",
  action: "#2F6FDE",
  isro: "#F26B21",
} as const;

export const font = {
  verdict: 40,
  title: 28,
  body: 18,
  small: 16,
} as const;

export const space = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } as const;

export const radius = { sm: 6, md: 12 } as const;

export const MIN_CONTRAST = 7;

/** WCAG relative luminance contrast ratio between two #RRGGBB colours. */
export function contrast(a: string, b: string): number {
  const lum = (hex: string) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** One-thumb targets (spec §17.10). */
export const touch = { min: 48 } as const;
