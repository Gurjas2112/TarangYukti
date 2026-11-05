// The whole story (spec §17.15): one TransitionSeries sequence per timeline scene, joined by 12-frame fades, the
// narration under each scene, and a chapter card at the start of each chapter. Fonts are the app's Noto fonts for
// the narration's script, copied into public/fonts by scripts/build_assets.py.
import { Audio } from "@remotion/media";
import { fade } from "@remotion/transitions/fade";
import { linearTiming, TransitionSeries } from "@remotion/transitions";
import { useEffect, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, staticFile } from "remotion";

import { ChapterCard, colors } from "./components";
import { SCENES } from "./scenes";
import type { StoryProps, Timeline } from "./types";

export const FPS = 30;
export const FADE = 12;

export const sceneFrames = (seconds: number) => Math.max(FADE + 1, Math.round(seconds * FPS));

function useFont(t: Timeline | undefined): string {
  const fallback = "'Noto Sans', system-ui, sans-serif";
  const [family, setFamily] = useState(fallback);
  const [handle] = useState(() => delayRender("narration font"));
  useEffect(() => {
    const f = t?.font;
    if (!f) {
      continueRender(handle);
      return;
    }
    const faces = [
      new FontFace(f.family, `url(${staticFile(f.regular)})`, { weight: "400" }),
      new FontFace(f.family, `url(${staticFile(f.bold)})`, { weight: "700" }),
    ];
    Promise.all(faces.map((x) => x.load()))
      .then((loaded) => {
        loaded.forEach((x) => document.fonts.add(x));
        setFamily(`'${f.family}', ${fallback}`);
      })
      .finally(() => continueRender(handle));
  }, [t, handle]);
  return family;
}

export function Story({ layout, timeline }: StoryProps) {
  const family = useFont(timeline);
  if (!timeline) return <AbsoluteFill style={{ background: colors.deep }} />;
  let lastChapter = -1;
  return (
    <AbsoluteFill style={{ background: colors.deep }}>
      <TransitionSeries>
        {timeline.scenes.flatMap((scene, i) => {
          const Scene = SCENES[scene.kind];
          const firstOfChapter = scene.chapter !== lastChapter;
          lastChapter = scene.chapter;
          const items = [
            <TransitionSeries.Sequence key={scene.id} durationInFrames={sceneFrames(scene.seconds)}>
              <Scene scene={scene} layout={layout} family={family} />
              {firstOfChapter && scene.kind !== "title" ? (
                <ChapterCard n={scene.chapter} title={timeline.chapters[String(scene.chapter)] ?? ""} family={family} />
              ) : null}
              {scene.narration ? <Audio src={staticFile(scene.narration)} /> : null}
            </TransitionSeries.Sequence>,
          ];
          if (i < timeline.scenes.length - 1) {
            items.push(
              <TransitionSeries.Transition
                key={`${scene.id}-fade`}
                presentation={fade()}
                timing={linearTiming({ durationInFrames: FADE })}
              />,
            );
          }
          return items;
        })}
      </TransitionSeries>
    </AbsoluteFill>
  );
}
