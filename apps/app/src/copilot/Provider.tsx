import type { ReactNode } from "react";
import { CopilotKitProvider } from "@copilotkit/react-native/headless";

import { getEnv } from "../env";

type Props = {
  children: ReactNode;
  accessToken?: string;
  mode: "simple" | "expert";
  lang: string;
};

/** One provider for Android and web, pointed at ty-copilot (spec §17.8). */
export function CopilotProvider({ children, accessToken, mode, lang }: Props) {
  return (
    <CopilotKitProvider
      runtimeUrl={`${getEnv().COPILOT_URL}/api/copilotkit`}
      headers={accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined}
      properties={{ mode, lang }}
    >
      {children}
    </CopilotKitProvider>
  );
}
