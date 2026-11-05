// chapters.txt for video platforms ("00:00 Title"), or with --ranges one line per chapter: "<n> <first> <last>"
// frames, for rendering one MP4 per chapter (spec §17.15). Same frame arithmetic as src/Root.tsx.
import { readFileSync } from "node:fs";

const FPS = 30;
const FADE = 12;
const t = JSON.parse(readFileSync(process.argv[2], "utf8"));
const ranges = process.argv.includes("--ranges");
const frames = (s) => Math.max(FADE + 1, Math.round(s * FPS));
let at = 0;
const chapters = [];
t.scenes.forEach((s, i) => {
  const start = at;
  at += frames(s.seconds) - (i < t.scenes.length - 1 ? FADE : 0);
  const last = chapters[chapters.length - 1];
  if (!last || last.n !== s.chapter) chapters.push({ n: s.chapter, start, end: at - 1 });
  else last.end = at - 1;
});
for (const c of chapters) {
  if (ranges) console.log(`${c.n} ${c.start} ${c.end}`);
  else {
    const sec = Math.floor(c.start / FPS);
    const stamp = `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
    console.log(`${stamp} ${t.chapters[String(c.n)] ?? ""}`);
  }
}
