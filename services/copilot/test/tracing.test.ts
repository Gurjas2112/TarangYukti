import assert from "node:assert/strict";
import { test } from "node:test";

import { tracingEnabled, withTracing } from "../src/tracing.ts";

test("TraceRoot is off unless switched on, and never in live (SEC-14)", async () => {
  assert.equal(tracingEnabled({}), false);
  assert.equal(tracingEnabled({ TRACEROOT_ENABLED: "true", ENV: "local" }), true);
  assert.throws(() => tracingEnabled({ TRACEROOT_ENABLED: "true", ENV: "live" }), /test traffic only/);
  const listener = () => undefined;
  assert.equal(await withTracing(listener, {}), listener); // off: the listener is returned untouched
});
