// Free-form questions go to the agent through ty-copilot (spec §17.8): add the user's message, run the agent,
// return the final reply (already validated, translated and ending with the advisory footer).
import { useAgent, useCopilotKit } from "@copilotkit/react-native/headless";
import { useCallback, useState } from "react";

let seq = 0;
const newId = () => `m-${Date.now().toString(36)}-${(seq++).toString(36)}`;

export function useAsk() {
  const { agent } = useAgent({ agentId: "default" });
  const { copilotkit } = useCopilotKit();
  const [busy, setBusy] = useState(false);

  const ask = useCallback(
    async (text: string): Promise<string> => {
      setBusy(true);
      try {
        agent.addMessage({ id: newId(), role: "user", content: text });
        await copilotkit.runAgent({ agent });
        const last = [...agent.messages].reverse().find((m) => m.role === "assistant");
        return typeof last?.content === "string" ? last.content : "";
      } finally {
        setBusy(false);
      }
    },
    [agent, copilotkit],
  );
  return { ask, busy };
}
