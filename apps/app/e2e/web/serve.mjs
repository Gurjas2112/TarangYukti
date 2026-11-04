// Static server for the exported web build (dist/) with the SPA fallback nginx uses in Tier 1 (try_files).
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";

const root = normalize(join(import.meta.dirname, "..", "..", "dist"));
const port = Number(process.env.PORT ?? 8081);
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".ico": "image/x-icon", ".ttf": "font/ttf" };

createServer((req, res) => {
  const path = normalize(join(root, decodeURIComponent(new URL(req.url ?? "/", "http://x").pathname)));
  const file = path.startsWith(root) && existsSync(path) && statSync(path).isFile() ? path : join(root, "index.html");
  res.setHeader("Content-Type", types[extname(file)] ?? "application/octet-stream");
  createReadStream(file).pipe(res);
}).listen(port, "127.0.0.1", () => console.log(`serving ${root} on :${port}`));
