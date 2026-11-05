// Every language (spec §6.5): fonts for every script, no built-in language, production shows only released ones.
import { expect, test } from "@jest/globals";
import * as fs from "fs";
import * as path from "path";

import { allLanguages, availableLanguages } from "../src/i18n";
import { SCRIPT_KEYS, scriptOf } from "../src/ui/fonts";

const ROOT = path.resolve(__dirname, "..");

function files(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "__tests__" ? [] : files(p);
    return /\.(ts|tsx)$/.test(e.name) ? [p] : [];
  });
}

test("all 23 languages have a bundled Noto font for their script", () => {
  expect(allLanguages).toHaveLength(23);
  for (const l of allLanguages) {
    const script = scriptOf(l.code);
    expect(SCRIPT_KEYS).toContain(script);
    if (l.script !== "Latn") expect(script).not.toBe("Latn"); // never falls back to the Latin font
  }
  expect(scriptOf("ur-IN")).toBe("Nastaliq");
  expect(scriptOf("sat-IN")).toBe("Olck");
  expect(scriptOf("mni-IN")).toBe("Mtei");
});

test("right-to-left exactly for Urdu, Kashmiri and Sindhi", () => {
  expect(allLanguages.filter((l) => l.rtl).map((l) => l.code).sort()).toEqual(["ks-IN", "sd-IN", "ur-IN"]);
});

test("production offers only released languages; other builds offer all", () => {
  const released = allLanguages.filter((l) => l.status === "released").map((l) => l.code);
  expect(availableLanguages("production").map((l) => l.code)).toEqual(released);
  expect(availableLanguages("preview")).toHaveLength(23);
});

test("no language is hard-coded as a default in app code", () => {
  // Allowed: the catalogue map, the missing-key fallback, and en-IN as a *number format* (Western digits).
  const allowed = [/catalogues\.ts$/, /i18n[\\/]index\.ts$/];
  const code = /["'](?:[a-z]{2,3})-IN["']/g;
  const hits: string[] = [];
  for (const f of [...files(path.join(ROOT, "src")), ...files(path.join(ROOT, "app"))]) {
    if (allowed.some((a) => a.test(f))) continue;
    fs.readFileSync(f, "utf8")
      .split("\n")
      .forEach((line, i) => {
        const stripped = line.replace(/toLocale(?:Time|Date)?String\(\s*["']en-IN["']/g, "");
        if (code.test(stripped)) hits.push(`${path.relative(ROOT, f)}:${i + 1}: ${line.trim()}`);
        code.lastIndex = 0;
      });
  }
  expect(hits).toEqual([]);
});
