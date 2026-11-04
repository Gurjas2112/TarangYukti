// Free-form questions go to the agent through ty-copilot (spec §17.8): add the user's message, run the agent,
// return the final reply (validated, translated, ending with the advisory footer) and the agent's state for the
// app: Mission Control steps, map/ledger actions and citation cards.
import { useAgent, useCopilotKit } from "@copilotkit/react-native/headless";
import { useCallback, useState } from "react";

import type { CitationCard } from "../components/CitationChip";

let seq = 0;
const newId = () => `m-${Date.now().toString(36)}-${(seq++).toString(36)}`;

export type AgentTurn = {
  reply: string;
  answerId: string | null;
  mission: string[];
  uiActions: unknown[];
  citations: CitationCard[];
};

export function useAsk() {
  const { agent } = useAgent({ agentId: "default" });
  const { copilotkit } = useCopilotKit();
  const [busy, setBusy] = useState(false);

  const ask = useCallback(
    async (text: string): Promise<AgentTurn> => {
      setBusy(true);
      try {
        agent.addMessage({ id: newId(), role: "user", content: text });
        await copilotkit.runAgent({ agent });
        const last = [...agent.messages].reverse().find((m) => m.role === "assistant");
        const st = (agent.state ?? {}) as Record<string, unknown>;
        return {
          reply: typeof last?.content === "string" ? last.content : "",
          answerId: typeof st.answer_id === "string" ? st.answer_id : null,
          mission: Array.isArray(st.mission) ? (st.mission as string[]) : [],
          uiActions: Array.isArray(st.ui_actions) ? st.ui_actions : [],
          citations: Array.isArray(st.citations) ? (st.citations as CitationCard[]) : [],
        };
      } finally {
        setBusy(false);
      }
    },
    [agent, copilotkit],
  );
  return { ask, busy };
}
