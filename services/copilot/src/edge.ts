import type { IncomingMessage, ServerResponse } from "node:http";

export type NodeHandler = (req: IncomingMessage, res: ServerResponse) => unknown;

const HEALTH_PATHS = new Set(["/health"]);

/**
 * Wraps the CopilotKit listener: `/health` answers `ok`; when FRONTDOOR_ID is set (Tier 1), every other
 * request must carry the matching `x-azure-fdid` header or gets 403 (prompt §14, spec §15.2.1).
 */
export function withEdge(inner: NodeHandler, frontdoorId: string | undefined): NodeHandler {
  return (req, res) => {
    const path = (req.url ?? "/").split("?")[0];
    if (HEALTH_PATHS.has(path)) {
      res.writeHead(200, { "content-type": "text/plain", "cache-control": "no-store" });
      res.end("ok");
      return;
    }
    if (frontdoorId && req.headers["x-azure-fdid"] !== frontdoorId) {
      res.writeHead(403, { "content-type": "text/plain" });
      res.end("forbidden");
      return;
    }
    return inner(req, res);
  };
}
