// ty-copilot — CopilotKit runtime on Node 24 (native TypeScript type stripping), spec §17.8.
// The app's Authorization header (Supabase JWT) is forwarded to ty-agent, which verifies it.
import { createServer } from "node:http";

import { HttpAgent } from "@ag-ui/client"; // pinned to the version @copilotkit/runtime depends on
import { CopilotRuntime } from "@copilotkit/runtime/v2";
import { createCopilotNodeListener } from "@copilotkit/runtime/v2/node";

import { withEdge } from "./edge.ts";
import { withTracing } from "./tracing.ts";

const agentUrl = process.env.AGENT_URL ?? "http://127.0.0.1:8123";

const runtime = new CopilotRuntime({
  agents: {
    default: new HttpAgent({ url: `${agentUrl}/agent` }),
  },
});

const listener = await withTracing(createCopilotNodeListener({ runtime, basePath: "/api/copilotkit", cors: true }));

const port = Number(process.env.PORT ?? 8200);
createServer(withEdge(listener, process.env.FRONTDOOR_ID || undefined)).listen(port, () =>
  console.log(`ty-copilot listening on :${port}`),
);
