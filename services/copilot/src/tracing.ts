// TraceRoot for improvement runs only (spec §10.4, SEC-14): with TRACEROOT_ENABLED=true every request becomes a
// "copilot.request" span until the response finishes, so the agent's trace hangs under it. Request and response
// bodies are not captured. Refuses to start in live, and does nothing at all when the switch is off.
import type { IncomingMessage, ServerResponse } from "node:http";

type Listener = (req: IncomingMessage, res: ServerResponse) => unknown;

export function tracingEnabled(env: NodeJS.ProcessEnv = process.env): boolean {
  if (env.TRACEROOT_ENABLED !== "true") return false;
  if (env.ENV === "live") throw new Error("TraceRoot is for test traffic only (SEC-14): unset TRACEROOT_ENABLED in live");
  return true;
}

export async function withTracing(listener: Listener, env: NodeJS.ProcessEnv = process.env): Promise<Listener> {
  if (!tracingEnabled(env)) return listener;
  const { TraceRoot, observe } = await import("@traceroot-ai/traceroot");
  TraceRoot.initialize();
  process.once("SIGTERM", () => void TraceRoot.shutdown().finally(() => process.exit(0)));
  return (req, res) =>
    observe({ name: "copilot.request", type: "span", captureInput: false, captureOutput: false }, () => {
      return new Promise<void>((resolve) => {
        res.once("close", () => resolve());
        listener(req, res);
      });
    });
}
