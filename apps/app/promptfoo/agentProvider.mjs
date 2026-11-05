// promptfoo provider: one question to the agent's AG-UI endpoint (POST /agent), the way ty-copilot sends it.
// AGENT_URL defaults to the laptop agent (make agent).
import { randomUUID } from "node:crypto";

export default class AgentProvider {
  constructor(options) {
    this.url = (process.env.AGENT_URL || "http://127.0.0.1:8123") + "/agent";
    this.config = options?.config ?? {};
  }

  id() {
    return "tarangyukti-agent";
  }

  async callApi(prompt, context) {
    const vars = context?.vars ?? {};
    const body = {
      threadId: `pf-${randomUUID()}`,
      runId: randomUUID(),
      state: {},
      messages: [{ id: randomUUID(), role: "user", content: prompt }],
      tools: [],
      context: [],
      forwardedProps: { lang: vars.lang, mode: vars.mode ?? "simple" },
    };
    const res = await fetch(this.url, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify(body),
    });
    if (!res.ok) return { error: `agent HTTP ${res.status}` };
    const text = await res.text();
    // The validated reply arrives in MESSAGES_SNAPSHOT (last assistant message); streamed deltas are a fallback.
    let streamed = "";
    let snapshot = "";
    for (const line of text.split(/\r?\n/)) {
      if (!line.startsWith("data:")) continue;
      let ev;
      try {
        ev = JSON.parse(line.slice(5));
      } catch {
        continue; // keep-alive or partial line
      }
      if (ev.type === "RUN_ERROR") return { error: ev.message ?? "agent run error" };
      if (ev.type === "TEXT_MESSAGE_CONTENT" && typeof ev.delta === "string") streamed += ev.delta;
      if (ev.type === "MESSAGES_SNAPSHOT" && Array.isArray(ev.messages)) {
        const last = [...ev.messages].reverse().find((m) => m.role === "assistant" && typeof m.content === "string");
        if (last) snapshot = last.content;
      }
    }
    return { output: (snapshot || streamed).trim() };
  }
}
