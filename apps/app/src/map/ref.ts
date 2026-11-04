// The one map the agent drives through CopilotKit frontend tools (flyTo, showLayer, drawRoute, setTime).
import type { OceanMapHandle } from "./types";

export const mapRef: { current: OceanMapHandle | null } = { current: null };
