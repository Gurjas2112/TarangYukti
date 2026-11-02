import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { after, before, describe, it } from "node:test";

import { withEdge } from "../src/edge.ts";

function serve(frontdoorId: string | undefined): Promise<{ server: Server; url: string }> {
  const inner = (_req: unknown, res: import("node:http").ServerResponse) => {
    res.writeHead(200);
    res.end("inner");
  };
  const server = createServer(withEdge(inner, frontdoorId));
  return new Promise((resolve) =>
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address() as AddressInfo;
      resolve({ server, url: `http://127.0.0.1:${port}` });
    }),
  );
}

describe("withEdge (Front Door check)", () => {
  let s: { server: Server; url: string };
  before(async () => {
    s = await serve("fd-123");
  });
  after(() => s.server.close());

  it("health is exempt", async () => {
    const r = await fetch(`${s.url}/health`);
    assert.equal(r.status, 200);
    assert.equal(await r.text(), "ok");
  });
  it("direct origin request is 403", async () => {
    assert.equal((await fetch(`${s.url}/api/copilotkit`)).status, 403);
  });
  it("through Front Door is passed on", async () => {
    const r = await fetch(`${s.url}/api/copilotkit`, { headers: { "x-azure-fdid": "fd-123" } });
    assert.equal(r.status, 200);
    assert.equal(await r.text(), "inner");
  });
});

describe("withEdge without FRONTDOOR_ID (laptop)", () => {
  it("passes every request", async () => {
    const { server, url } = await serve(undefined);
    try {
      assert.equal((await fetch(`${url}/api/copilotkit`)).status, 200);
    } finally {
      server.close();
    }
  });
});
