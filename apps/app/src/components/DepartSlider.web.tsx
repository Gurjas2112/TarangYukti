// "Drag the departure" (spec §7.5): 0 to +24 h in 30-minute steps; the plan is re-evaluated for that time.
import { useTranslation } from "react-i18next";

import { colors } from "../ui/tokens";

export type DepartSliderProps = { steps: number; value: number; label: string; onChange: (step: number) => void };

export function DepartSlider({ steps, value, label, onChange }: DepartSliderProps) {
  const { t } = useTranslation();
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 260, color: colors.text, fontSize: 16 }}>
      <span style={{ fontWeight: 700 }}>{t("expert.depart")}</span>
      <input
        type="range"
        min={0}
        max={steps}
        step={1}
        value={value}
        data-testid="depart-slider"
        aria-label={t("expert.depart")}
        onChange={(e) => onChange(Number(e.currentTarget.value))}
        style={{ flex: 1, accentColor: colors.action }}
      />
      <span data-testid="depart-label" style={{ minWidth: 120 }}>
        {label}
      </span>
    </label>
  );
}
