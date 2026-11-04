// CI key check (spec §6.5): every catalogue has every key of en-IN.json with the same {{variables}}, and every
// released language has no key left in English (drafts.json). Exit 1 with the problems.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "i18n");
const read = (f) => JSON.parse(readFileSync(join(dir, f), "utf-8"));
const en = read("en-IN.json");
const languages = read("languages.json");
const drafts = read("drafts.json");
const vars = (s) => (s.match(/\{\{\s*\w+\s*\}\}/g) ?? []).sort().join(",");
const problems = [];

for (const lang of languages) {
  let cat;
  try {
    cat = read(`${lang.code}.json`);
  } catch {
    problems.push(`${lang.code}: catalogue missing`);
    continue;
  }
  for (const [key, text] of Object.entries(en)) {
    if (typeof cat[key] !== "string") problems.push(`${lang.code}: missing ${key}`);
    else if (vars(cat[key]) !== vars(text)) problems.push(`${lang.code}: {{variables}} differ in ${key}`);
  }
  if (lang.status === "released" && (drafts[lang.code]?.ui ?? []).length) {
    problems.push(`${lang.code}: released but ${drafts[lang.code].ui.length} strings are still English`);
  }
}

if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log(`i18n: ${languages.length} catalogues, ${Object.keys(en).length} keys each — ok`);
