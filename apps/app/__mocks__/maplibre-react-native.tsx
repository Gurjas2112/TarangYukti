// Jest stand-in for @maplibre/maplibre-react-native (a native map cannot render in Node). Each GeoJSON source
// renders as a View with testID "source-<id>", and the camera records its last flyTo in a View's testID.
import { forwardRef, type ReactNode, useImperativeHandle, useState } from "react";
import { View } from "react-native";

export const Map = ({ children }: { children?: ReactNode }) => <View testID="maplibre">{children}</View>;
export const GeoJSONSource = ({ id, children }: { id: string; children?: ReactNode }) => (
  <View testID={`source-${id}`}>{children}</View>
);
export const Layer = () => null;
export const UserLocation = () => null;
export const Camera = forwardRef(function Camera(
  { initialViewState }: { initialViewState?: { center?: [number, number] } },
  ref,
) {
  const [center, setCenter] = useState<[number, number] | undefined>(initialViewState?.center);
  useImperativeHandle(ref, () => ({ flyTo: (o: { center: [number, number] }) => setCenter(o.center) }));
  return <View testID={`camera-${center?.[1].toFixed(3)},${center?.[0].toFixed(3)}`} />;
});
