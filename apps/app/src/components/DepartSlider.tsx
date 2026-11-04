// Native fallback: step buttons (the Expert console is a web screen; this keeps the contract on both targets).
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, font, space, touch } from "../ui/tokens";

export type DepartSliderProps = { steps: number; value: number; label: string; onChange: (step: number) => void };

export function DepartSlider({ steps, value, label, onChange }: DepartSliderProps) {
  return (
    <View style={styles.row} testID="depart-slider">
      <Pressable style={styles.b} onPress={() => onChange(Math.max(0, value - 1))} accessibilityRole="button" accessibilityLabel="−30 min">
        <Text style={styles.t}>−</Text>
      </Pressable>
      <Text style={styles.t} testID="depart-label">
        {label}
      </Text>
      <Pressable style={styles.b} onPress={() => onChange(Math.min(steps, value + 1))} accessibilityRole="button" accessibilityLabel="+30 min">
        <Text style={styles.t}>+</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: space.sm },
  b: { minWidth: touch.min, minHeight: touch.min, borderWidth: 2, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  t: { fontSize: font.body, color: colors.text },
});
